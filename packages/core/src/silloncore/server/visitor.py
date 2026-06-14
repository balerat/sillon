from silloncore.simulation import Simulations_object as Simulations


class CommandVisitor:
    def visit_log_result(self, command, key):
        # If the result to save is a None value, an exception is raised
        if command.value is None:
            raise Exception("NoValue")
        else:
            Simulations.sim_dict[key].log_result(command.name, command.value)

    def visit_log_param(self, command, key):
        # If the parameter to save is a None value, an exception is raised
        if command.value is None:
            raise Exception("NoValue")
        else:
            Simulations.sim_dict[key].log_param(command.name, command.value)

    def visit_log_figure(self, command, key):
        # If the figure to save is a None value, an exception is raised
        if command.value is None:
            raise Exception("NoValue")
        else:
            Simulations.sim_dict[key].log_figure(command.name, command.value)

    def visit_add_metadata(self, command, key):
        # If the meta data to save is a None value, an exception is raised
        if command.value is None:
            raise Exception("NoValue")
        else:
            Simulations.sim_dict[key].add_metadata(command.name, command.value)

    def visit_add_tag(self, command, key):
        # If the meta data to save is a None value, an exception is raised
        if command.value is None:
            raise Exception("NoValue")
        else:
            Simulations.sim_dict[key].add_tag(command.name, command.value)

    def visit_add_note(self, command, key):
        # If the meta data to save is a None value, an exception is raised
        if command.value is None:
            raise Exception("NoValue")
        else:
            Simulations.sim_dict[key].add_note(command.name, command.value)

    def visit_load_result(self, command, key):
        return Simulations.sim_dict[key].get_result(command.name)

    def visit_load_param(self, command, key):
        return Simulations.sim_dict[key].get_param(command.name)

    def visit_load_metadata(self, command, key):
        return Simulations.sim_dict[key].get_metadata(command.name)

    def visit_shutdown(self):
        return None  # Returning nothing : the server will shut down

    def visit_dump(self):
        return None  # Returning nothing : the server will shut down

