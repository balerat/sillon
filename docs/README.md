 ░▒▓███████▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓██████▓▒░░▒▓███████▓▒░  
░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
 ░▒▓██████▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
       ░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
       ░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓███████▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓████████▓▒░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░ 


## What is the project?
Sillon is a devtool chain aimed at logging and tracking simulation runs on any platform. You can think of it as the "Git for simulations." It is platform-agnostic, intuitive, and easy to use. 
It is a multiplatform tool to track simulation metadata, data and let users collaborate on simulation together. It does simulation control, colaboration, data organisation so you never have to loose yourself in endless simulation result of everchanging code that doesn't make a sense anymore.

Sillon can log simulation parameters, metadata, tags, and results. The toolchain comes with a GUI, a collaborative web platform, a CLI tool with Slurm integration, and an analysis library. Ultimately, there will be a native API for each major platform (Python, C++, etc.).

## Documentation
The documentation is accessible [**HERE**](https://simply-docs-hub.pages.dev/)

## The project is composed in different part which are:

 - A python library to track simulations (pysimtrack)
 - A cli tool to launch and track simulation for differe codebase / software 
 - A gui to keep track and order projects
 - A web interface to colaborate and save data result
 - A DAG and task manager tool

## The goal of Sillon is:
- To be less intrusive as possible: The user need only a little knowledge of the library and has little to do to make it work. It also doesn't have to change the way he write his code for him to use this tool.
- To be as flexible as possible: The user must be able to track any type of data on an type of platform in any type of way with any type of code or software.
- Create a smart philosophy for simulation tracking: Using existing and novel ways the libraries stores and treats simulation run in the most sensible way.
- Fast and pretty: The tool must be fast, smart, optimized for big data structure, big codebase and must be pretty for its interface.

