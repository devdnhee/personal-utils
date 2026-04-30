# Repository to markdown compression

Write a python script that:
- (encode) compresses a github repository to a single markdown file.
- (decode) decompresses the markdown file back to a directory in exactly the same state as the original input

## encode

Encoding places all raw content as text in markdown.
ONLY consider files which are not in .gitignore. (`git ls-files`)

Example:

a repo has the following structure:
```
repo                                                                                  
  ├── A/                                                                               
  │   ├── file1.py                              
  │   └── file2.py
  ├── B/                                                                               
  │   └── file3.txt
  └── C/                                                                               
      ├── C1/     
      │   └── file4.txt                                                                
      └── file5.py
```

The output should look like this:
```markdown
# repo

## A

### file1.py
content file1

### file2.py
content file2

## B

### file3.txt
content file3

## C

### C1

#### file4.txt
content file4

### file5.py
content file5
```

If the user provides an output file as arg with .docx file extension, convert to .docx.

## decode
Decoding inverses the encoding process, so from a markdown or docx file back to a directory structure, writing all files in the correct file structure.

The directory where the file are generated should be the h1 header of the input      
markdown file, so args.output/<h1_header>.

When the repository already exists, there exist different modes to handle conflicting files:
- overwrite: overwrites conflicting files with the new file
- append: appends content from the new file to the old file, separated by '----'
- ignore: keep the old file exactly as is
- block: raise an error

ALWAYS log what type of change you make to each conflicting file. 

## Requirements
It has the following requirements:
- functions:
    - encode
        - Args:
            - required: github repository: local path
            - -o / --output: output file, by default to `output.md`
    - decode
        - Args:
            - required: input file
            - -m / --mode: 'overwrite', 'append', 'ignore', 'block'
            - -o / --output: output path, by default to `.`
- Args: 
    - required arg github repository: local path
    - -o / --output: output file, by default to `data/images/<%y-%m-%d>_stars.html`
    - -w / --word: conversion to .docx at the end, file is stored with `.docx` file extension