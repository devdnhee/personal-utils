Write a python script that plots the number of stars for a given github repository over time.
It has the following requirements:
- Args: 
    - required arg github repository: either a URL or format `owner/repo`
    - -o / --output: output file, by default to `data/images/<%y-%m-%d>_stars.html`
- Requirements:
    - x-axis: time
    - y-axis: amount of stars
    - Use plotly for plotting
    - output format is derived from file extension in `--output`
    - Use sufficient logging
- Output:
    - image written to output file