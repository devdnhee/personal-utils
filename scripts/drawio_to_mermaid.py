# /// script
# dependencies = [
#   "fire>=0.7.0",
# ]
# requires-python = ">=3.12"
# ///

"""Convert draw.io (.drawio) diagrams to Mermaid flowchart format.

Supported draw.io features:
  - Node shapes: rectangle, rounded, diamond, circle/ellipse, cylinder,
                 stadium, hexagon, subroutine, parallelogram, asymmetric
  - Edge styles: solid (-->), dotted (-.->) , thick (==>), no-arrow (---)
  - Edge labels
  - Both plain-XML and compressed (deflate + base64) diagram content

Usage:
    uv run scripts/drawio_to_mermaid.py diagram.drawio
    uv run scripts/drawio_to_mermaid.py diagram.drawio --output_path=out.mmd
    uv run scripts/drawio_to_mermaid.py diagram.drawio --direction=LR
"""

import base64
import os
import re
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field

import fire


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Node:
    id: str          # safe mermaid identifier
    label: str
    shape: str = "rectangle"


@dataclass
class Edge:
    source: str      # draw.io cell id
    target: str      # draw.io cell id
    label: str = ""
    style: str = "solid"


# ---------------------------------------------------------------------------
# Style detection helpers
# ---------------------------------------------------------------------------


def _detect_node_shape(style: str) -> str:
    """Map a draw.io cell style string to a mermaid shape name."""
    if "shape=mxgraph.flowchart.database" in style:
        return "cylinder"
    if "shape=mxgraph.flowchart.start_2" in style:
        return "stadium"
    if "shape=hexagon" in style:
        return "hexagon"
    if "shape=process" in style:
        return "subroutine"
    if "shape=parallelogram" in style:
        return "parallelogram"
    if "shape=mxgraph.arrows2.arrow" in style:
        return "asymmetric"
    if "rhombus" in style:
        return "diamond"
    if "ellipse" in style:
        return "circle"
    # rounded=1 with a high arcSize is how mermaid_to_drawio encodes stadium-like
    # rounded nodes; arcSize=50 is the specific value used for mermaid "rounded"
    if "arcSize=50" in style or re.search(r"rounded=1\b", style):
        return "rounded"
    return "rectangle"


def _detect_edge_style(style: str) -> str:
    """Map a draw.io edge style string to a mermaid edge style name."""
    if "dashed=1" in style:
        return "dotted"
    if "strokeWidth=3" in style:
        return "thick"
    if "endArrow=none" in style:
        return "no_arrow"
    return "solid"


# ---------------------------------------------------------------------------
# Label sanitisation
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"\s+")


def _clean_label(raw: str) -> str:
    """Strip HTML tags and normalise whitespace in a draw.io cell value."""
    text = _HTML_TAG_RE.sub("", raw)
    return _MULTI_SPACE_RE.sub(" ", text).strip()


# ---------------------------------------------------------------------------
# Mermaid rendering
# ---------------------------------------------------------------------------

_NODE_FMT: dict[str, str] = {
    "rectangle":    "[{label}]",
    "rounded":      "({label})",
    "diamond":      "{{{label}}}",
    "circle":       "(({label}))",
    "cylinder":     "[({label})]",
    "stadium":      "([{label}])",
    "hexagon":      "{{{{{label}}}}}",
    "subroutine":   "[[{label}]]",
    "parallelogram": "[/{label}/]",
    "asymmetric":   ">{label}]",
}

_EDGE_ARROW: dict[str, str] = {
    "solid":    "-->",
    "dotted":   "-.->",
    "thick":    "==>",
    "no_arrow": "---",
}

_EDGE_LABEL_ARROW: dict[str, str] = {
    "solid":    "-- {label} -->",
    "dotted":   "-. {label} .->",
    "thick":    "== {label} ==>",
    "no_arrow": "-- {label} ---",
}


def _render_node(node: Node) -> str:
    fmt = _NODE_FMT.get(node.shape, "[{label}]")
    return f"    {node.id}{fmt.format(label=node.label)}"


def _render_edge(edge: Edge, id_map: dict[str, str]) -> str:
    src = id_map.get(edge.source, edge.source)
    tgt = id_map.get(edge.target, edge.target)
    if edge.label:
        connector = _EDGE_LABEL_ARROW.get(edge.style, "-- {label} -->").format(
            label=edge.label
        )
    else:
        connector = _EDGE_ARROW.get(edge.style, "-->")
    return f"    {src} {connector} {tgt}"


# ---------------------------------------------------------------------------
# draw.io XML parsing
# ---------------------------------------------------------------------------


def _decompress_diagram(text: str) -> str:
    """Decompress base64+raw-deflate encoded draw.io diagram text."""
    # draw.io omits the zlib header; padding may be missing
    padding = (4 - len(text) % 4) % 4
    data = base64.b64decode(text + "=" * padding)
    return zlib.decompress(data, wbits=-15).decode("utf-8")


def _find_graph_model(root: ET.Element) -> ET.Element | None:
    """Return the mxGraphModel element, decompressing if needed."""
    gm = root.find(".//mxGraphModel")
    if gm is not None:
        return gm

    diagram = root.find(".//diagram")
    if diagram is not None and diagram.text and diagram.text.strip():
        try:
            xml_str = _decompress_diagram(diagram.text.strip())
            inner = ET.fromstring(xml_str)
            if inner.tag == "mxGraphModel":
                return inner
            return inner.find(".//mxGraphModel")
        except Exception:
            pass

    return None


def _safe_id(raw: str, seen: dict[str, str]) -> str:
    """Convert an arbitrary draw.io cell id to a valid mermaid identifier."""
    sanitised = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    if sanitised and sanitised[0].isdigit():
        sanitised = "n" + sanitised
    if not sanitised:
        sanitised = "node"

    # Deduplicate
    candidate = sanitised
    counter = 1
    while candidate in seen.values() and seen.get(raw) != candidate:
        candidate = f"{sanitised}_{counter}"
        counter += 1
    return candidate


def _parse_drawio(
    xml_content: str,
) -> tuple[dict[str, Node], list[Edge], dict[str, str], str]:
    """Parse draw.io XML.

    Returns:
        nodes:   cell_id → Node
        edges:   list of Edge (using original draw.io cell ids for source/target)
        id_map:  draw.io cell_id → mermaid-safe identifier
        direction: inferred 'TD' or 'LR'
    """
    root_el = ET.fromstring(xml_content)
    gm = _find_graph_model(root_el)
    if gm is None:
        return {}, [], {}, "TD"

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    id_map: dict[str, str] = {}
    positions: dict[str, tuple[float, float]] = {}

    for cell in gm.iter("mxCell"):
        cell_id = cell.get("id", "")
        if cell_id in ("0", "1"):
            continue

        value = _clean_label(cell.get("value", ""))
        style = cell.get("style", "")

        if cell.get("vertex") == "1":
            safe = _safe_id(cell_id, id_map)
            id_map[cell_id] = safe
            shape = _detect_node_shape(style)
            nodes[cell_id] = Node(id=safe, label=value or safe, shape=shape)

            geo = cell.find("mxGeometry")
            if geo is not None:
                try:
                    positions[cell_id] = (
                        float(geo.get("x", 0)),
                        float(geo.get("y", 0)),
                    )
                except ValueError:
                    pass

        elif cell.get("edge") == "1":
            src = cell.get("source", "")
            tgt = cell.get("target", "")
            if src and tgt:
                edges.append(
                    Edge(
                        source=src,
                        target=tgt,
                        label=value,
                        style=_detect_edge_style(style),
                    )
                )

    direction = _infer_direction(positions)
    return nodes, edges, id_map, direction


def _infer_direction(positions: dict[str, tuple[float, float]]) -> str:
    """Guess TD vs LR from the bounding box of node positions."""
    if len(positions) < 2:
        return "TD"
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)
    return "LR" if x_span > y_span else "TD"


# ---------------------------------------------------------------------------
# Mermaid output assembly
# ---------------------------------------------------------------------------


def _build_mermaid(
    nodes: dict[str, Node],
    edges: list[Edge],
    id_map: dict[str, str],
    direction: str,
) -> str:
    lines: list[str] = [f"flowchart {direction}"]

    # Declare all nodes
    for node in nodes.values():
        lines.append(_render_node(node))

    if nodes and edges:
        lines.append("")  # blank separator

    # Render edges (skip any referencing unknown nodes)
    known = set(nodes)
    for edge in edges:
        if edge.source in known and edge.target in known:
            lines.append(_render_edge(edge, id_map))

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def convert(
    input_path: str,
    output_path: str = None,
    direction: str = None,
) -> None:
    """Convert a draw.io diagram to Mermaid flowchart format.

    :param input_path:  Path to a .drawio file.
    :param output_path: Destination .mmd file. Defaults to
                        <input_stem>.mmd next to the source file.
    :param direction:   Override the inferred flow direction
                        (TD, LR, RL, BT). Auto-detected when omitted.
    """
    if not os.path.exists(input_path):
        print(f"Error: '{input_path}' not found.")
        return

    if output_path is None:
        stem = os.path.splitext(input_path)[0]
        output_path = f"{stem}.mmd"

    with open(input_path, encoding="utf-8") as f:
        content = f.read()

    nodes, edges, id_map, inferred_dir = _parse_drawio(content)

    if not nodes:
        print("Warning: no nodes found. Is this a supported draw.io flowchart?")
        return

    final_dir = direction.upper() if direction else inferred_dir
    mermaid_output = _build_mermaid(nodes, edges, id_map, final_dir)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(mermaid_output)

    print(
        f"Converted {len(nodes)} node(s) and {len(edges)} edge(s)  →  {output_path}"
    )


if __name__ == "__main__":
    fire.Fire(convert)
