# /// script
# dependencies = [
#   "fire>=0.7.0",
# ]
# requires-python = ">=3.12"
# ///

"""Convert Mermaid flowchart diagrams to draw.io (.drawio) XML format.

Supported Mermaid features:
  - Diagram types: graph / flowchart (TD, TB, LR, RL, BT)
  - Node shapes: rectangle [], rounded (), diamond {}, circle (()),
                 cylinder [()] , stadium ([]), hexagon {{}},
                 subroutine [[]], parallelogram [//], asymmetric >]
  - Edge styles: solid (-->), dotted (-.->) , thick (==>), no-arrow (---)
  - Edge labels: -->|label| and -- label --> syntax
  - Markdown fenced code blocks (```mermaid ... ```)

Usage:
    uv run scripts/mermaid_to_drawio.py diagram.mmd
    uv run scripts/mermaid_to_drawio.py diagram.mmd --output_path=out.drawio
"""

import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional
from xml.dom import minidom

import fire


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Node:
    id: str
    label: str
    shape: str = "rectangle"


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""
    style: str = "solid"


# ---------------------------------------------------------------------------
# Node shape patterns (order matters – most specific first)
# ---------------------------------------------------------------------------

_SHAPE_PATTERNS: list[tuple[str, str]] = [
    (r"(\w[\w\-]*)\[\[(.+?)\]\]", "subroutine"),
    (r"(\w[\w\-]*)\[\((.+?)\)\]", "cylinder"),
    (r"(\w[\w\-]*)\(\[(.+?)\]\)", "stadium"),
    (r"(\w[\w\-]*)\(\((.+?)\)\)", "circle"),
    (r"(\w[\w\-]*)\{\{(.+?)\}\}", "hexagon"),
    (r"(\w[\w\-]*)\[\/(.+?)\/\]", "parallelogram"),
    (r"(\w[\w\-]*)\[\\(.+?)\\\]", "parallelogram_r"),
    (r"(\w[\w\-]*)\[\/(.+?)\\\]", "trapezoid"),
    (r"(\w[\w\-]*)\[\\(.+?)\/\]", "trapezoid_r"),
    (r"(\w[\w\-]*)\[(.+?)\]", "rectangle"),
    (r"(\w[\w\-]*)\((.+?)\)", "rounded"),
    (r"(\w[\w\-]*)\{(.+?)\}", "diamond"),
    (r"(\w[\w\-]*)>(.+?)\]", "asymmetric"),
]

# Edge patterns: (regex, style, has_inline_label)
_EDGE_PATTERNS: list[tuple[str, str, bool]] = [
    # Labeled: -->|label|
    (r"^(.+?)\s*--+>\s*\|([^|]*)\|\s*(.+)$", "solid", True),
    # Labeled: -- label -->
    (r"^(.+?)\s*--\s+(.+?)\s+--+>\s*(.+)$", "solid", True),
    # Labeled dotted: -.-|label|->
    (r"^(.+?)\s*-\.->\s*\|([^|]*)\|\s*(.+)$", "dotted", True),
    # Labeled dotted: -. label .->
    (r"^(.+?)\s*-\.\s+(.+?)\s+\.->\s*(.+)$", "dotted", True),
    # Labeled thick: ==>|label|
    (r"^(.+?)\s*==+>\s*\|([^|]*)\|\s*(.+)$", "thick", True),
    # Labeled thick: == label ==>
    (r"^(.+?)\s*==\s+(.+?)\s+==+>\s*(.+)$", "thick", True),
    # Plain arrows
    (r"^(.+?)\s*--+>\s*(.+)$", "solid", False),
    (r"^(.+?)\s*-\.->\s*(.+)$", "dotted", False),
    (r"^(.+?)\s*==+>\s*(.+)$", "thick", False),
    (r"^(.+?)\s*---\s*(.+)$", "no_arrow", False),
]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_node_str(s: str, nodes: dict[str, Node]) -> Optional[str]:
    """Parse a node token like 'A[label]' or bare 'A'; return the node id."""
    s = s.strip()
    if not s:
        return None

    for pattern, shape in _SHAPE_PATTERNS:
        m = re.fullmatch(pattern, s)
        if m:
            nid, label = m.group(1), m.group(2)
            # Always update so that the first definition with a label wins
            if nid not in nodes:
                nodes[nid] = Node(id=nid, label=label, shape=shape)
            else:
                nodes[nid].label = label
                nodes[nid].shape = shape
            return nid

    # Plain identifier with no shape decoration
    m = re.fullmatch(r"(\w[\w\-]*)", s)
    if m:
        nid = m.group(1)
        if nid not in nodes:
            nodes[nid] = Node(id=nid, label=nid, shape="rectangle")
        return nid

    return None


def _parse_line(
    line: str, nodes: dict[str, Node], edges: list[Edge]
) -> None:
    """Try to parse one mermaid line and update nodes/edges in-place."""
    line = line.strip().rstrip(";")
    if not line or line.startswith("%%"):
        return

    for pattern, style, has_label in _EDGE_PATTERNS:
        m = re.match(pattern, line)
        if not m:
            continue

        if has_label:
            src_s, label, tgt_s = m.group(1), m.group(2), m.group(3)
        else:
            src_s, tgt_s, label = m.group(1), m.group(2), ""

        src_id = _parse_node_str(src_s.strip(), nodes)
        tgt_id = _parse_node_str(tgt_s.strip(), nodes)
        if src_id and tgt_id:
            edges.append(
                Edge(source=src_id, target=tgt_id, label=label.strip(), style=style)
            )
        return

    # No edge found – try as a standalone node definition
    _parse_node_str(line, nodes)


def parse_mermaid(content: str) -> tuple[dict[str, Node], list[Edge], str]:
    """Parse mermaid flowchart content into nodes, edges and layout direction."""
    lines = content.strip().splitlines()
    if not lines:
        return {}, [], "TD"

    direction = "TD"
    m = re.match(
        r"^\s*(?:graph|flowchart)\s+(TD|TB|LR|RL|BT)\b", lines[0], re.IGNORECASE
    )
    if m:
        direction = m.group(1).upper()

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    in_subgraph = False

    for raw in lines[1:]:
        stripped = raw.strip()
        if re.match(r"^subgraph\b", stripped):
            in_subgraph = True
            continue
        if stripped == "end" and in_subgraph:
            in_subgraph = False
            continue
        _parse_line(stripped, nodes, edges)

    return nodes, edges, direction


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def _layout_nodes(
    nodes: dict[str, Node], edges: list[Edge], direction: str
) -> dict[str, tuple[float, float]]:
    """Assign (x, y) coordinates using a simple BFS layered layout."""
    children: dict[str, list[str]] = defaultdict(list)
    in_deg: dict[str, int] = {nid: 0 for nid in nodes}

    for e in edges:
        if e.source in nodes and e.target in nodes:
            children[e.source].append(e.target)
            in_deg[e.target] += 1

    # BFS from roots to assign layers; handle cycles by ignoring back-edges
    layer: dict[str, int] = {}
    queue: deque[str] = deque(
        nid for nid, deg in in_deg.items() if deg == 0
    )
    # Fallback: if all nodes have in-degree > 0 (pure cycle), start from first
    if not queue:
        queue.append(next(iter(nodes)))

    while queue:
        nid = queue.popleft()
        current_layer = layer.get(nid, 0)
        for child in children[nid]:
            new_layer = current_layer + 1
            if child not in layer or layer[child] < new_layer:
                layer[child] = new_layer
                queue.append(child)

    # Assign layer 0 to any nodes still missing (disconnected)
    for nid in nodes:
        layer.setdefault(nid, 0)

    # Group by layer
    by_layer: dict[int, list[str]] = defaultdict(list)
    for nid, lyr in layer.items():
        by_layer[lyr].append(nid)

    NODE_W, NODE_H = 140, 60
    H_GAP, V_GAP = 50, 60
    MARGIN = 60
    horizontal = direction in ("LR", "RL")

    positions: dict[str, tuple[float, float]] = {}
    for lyr_idx in sorted(by_layer):
        layer_nodes = by_layer[lyr_idx]
        for slot, nid in enumerate(layer_nodes):
            if horizontal:
                x = MARGIN + lyr_idx * (NODE_W + H_GAP)
                y = MARGIN + slot * (NODE_H + V_GAP)
            else:
                x = MARGIN + slot * (NODE_W + H_GAP)
                y = MARGIN + lyr_idx * (NODE_H + V_GAP)
            positions[nid] = (x, y)

    return positions


# ---------------------------------------------------------------------------
# draw.io XML builder
# ---------------------------------------------------------------------------

_NODE_STYLES: dict[str, str] = {
    "rectangle": "rounded=0;whiteSpace=wrap;html=1;",
    "rounded": "rounded=1;arcSize=50;whiteSpace=wrap;html=1;",
    "diamond": "rhombus;whiteSpace=wrap;html=1;",
    "circle": "ellipse;whiteSpace=wrap;html=1;aspect=fixed;",
    "cylinder": "shape=mxgraph.flowchart.database;whiteSpace=wrap;html=1;",
    "stadium": "shape=mxgraph.flowchart.start_2;whiteSpace=wrap;html=1;",
    "hexagon": "shape=hexagon;whiteSpace=wrap;html=1;",
    "subroutine": "shape=process;whiteSpace=wrap;html=1;",
    "parallelogram": "shape=parallelogram;whiteSpace=wrap;html=1;",
    "parallelogram_r": "shape=parallelogram;flipH=1;whiteSpace=wrap;html=1;",
    "trapezoid": "shape=trapezoid;whiteSpace=wrap;html=1;",
    "trapezoid_r": "shape=trapezoid;flipH=1;whiteSpace=wrap;html=1;",
    "asymmetric": "shape=mxgraph.arrows2.arrow;whiteSpace=wrap;html=1;",
}

_EDGE_STYLES: dict[str, str] = {
    "solid": "edgeStyle=orthogonalEdgeStyle;html=1;",
    "dotted": "edgeStyle=orthogonalEdgeStyle;dashed=1;html=1;",
    "thick": "edgeStyle=orthogonalEdgeStyle;strokeWidth=3;html=1;",
    "no_arrow": "edgeStyle=orthogonalEdgeStyle;endArrow=none;html=1;",
}


def _build_drawio_xml(
    nodes: dict[str, Node],
    edges: list[Edge],
    positions: dict[str, tuple[float, float]],
) -> str:
    NODE_W, NODE_H = 140, 60

    mxfile = ET.Element(
        "mxfile",
        {"host": "mermaid-to-drawio", "version": "21.0.0"},
    )
    diagram = ET.SubElement(mxfile, "diagram", {"name": "Page-1", "id": "page-1"})
    graph_model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "1169",
            "pageHeight": "827",
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(graph_model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    for nid, node in nodes.items():
        x, y = positions.get(nid, (60.0, 60.0))
        style = _NODE_STYLES.get(node.shape, _NODE_STYLES["rectangle"])
        # Diamonds need more width to look right
        w = NODE_W * 1.4 if node.shape == "diamond" else NODE_W
        h = NODE_H * 1.4 if node.shape in ("diamond", "circle") else NODE_H

        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": f"n-{nid}",
                "value": node.label,
                "style": style,
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"},
        )

    for i, edge in enumerate(edges):
        style = _EDGE_STYLES.get(edge.style, _EDGE_STYLES["solid"])
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": f"e-{i}",
                "value": edge.label,
                "style": style,
                "edge": "1",
                "source": f"n-{edge.source}",
                "target": f"n-{edge.target}",
                "parent": "1",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    raw = ET.tostring(mxfile, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")
    # Strip the redundant XML declaration that minidom prepends
    lines = pretty.splitlines()
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def convert(input_path: str, output_path: str = None) -> None:
    """Convert a Mermaid flowchart file to draw.io format.

    :param input_path: Path to a .mmd file or a Markdown file with a
                       fenced ```mermaid block.
    :param output_path: Destination .drawio file. Defaults to
                        <input_stem>.drawio next to the source file.
    """
    import os

    if not os.path.exists(input_path):
        print(f"Error: '{input_path}' not found.")
        return

    if output_path is None:
        stem = os.path.splitext(input_path)[0]
        output_path = f"{stem}.drawio"

    with open(input_path, encoding="utf-8") as f:
        content = f.read()

    # Strip markdown fences if present
    content = re.sub(r"^```mermaid\s*\n", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n```\s*$", "", content, flags=re.MULTILINE)
    content = content.strip()

    nodes, edges, direction = parse_mermaid(content)

    if not nodes:
        print("Warning: no nodes found. Is this a supported mermaid flowchart?")
        return

    positions = _layout_nodes(nodes, edges, direction)
    xml_output = _build_drawio_xml(nodes, edges, positions)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_output)

    print(
        f"Converted {len(nodes)} node(s) and {len(edges)} edge(s)  →  {output_path}"
    )


if __name__ == "__main__":
    fire.Fire(convert)
