# sillonPy API Reference

A python client to use sillon. It will look like all the apis for each new support in the future. It works with a tracker object that will upon creation connect to the server to register a new simulation, wrap each api call to a command sent to the server, and close the simulation and ask the server to dump the run.

## Architecture:
- api.py: The code of all the function for the user to use to interact with sillon
- tracker.py: The tracker object that will wrap the api function to send command to the server.
- metadata.py: A collection of function to get python specific metadata.
- servercom.py: Some python function to comunicate with the server.

## Api calls:
For now the python api offers:
- log_param(key,value / dict): Log a parameter.
- log_result(key, path, save_result:opt / key, data, save_result:opt_): Will save a result as an artifact or in the glob.
- log_metadata(key, value): Log a metadata.
- add_note(note): Add a note regarding the simulation.
- add_tag(tag / list): Add one or more tag to the future run.
- track(run_name, save_result:opt): A function to call at the begginign of the simulation to track the run and a wrapper for function to track specific instances.

::: sillonpy
    options:
        show_submodules: true
