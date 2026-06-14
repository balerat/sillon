
class Command:
    def __init__(self, name, method, value=""):
        self.name = name
        self.value = value
        self.method = method

    def accept(self, visitor, key):
        return None


class LogResultCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "log_result", value)

    def accept(self, visitor, key):
        visitor.visit_log_result(self, key)


class LogParamCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "log_param", value)

    def accept(self, visitor, key):
        visitor.visit_log_param(self, key)


class LogFigureCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "log_figure", value)

    def accept(self, visitor, key):
        visitor.visit_log_figure(self, key)


class AddMetaDataCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "add_metadata", value)

    def accept(self, visitor, key):
        visitor.visit_add_metadata(self, key)


class AddNoteCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "add_note", value)

    def accept(self, visitor, key):
        visitor.visit_add_note(self, key)


class AddTagCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "add_tag", value)

    def accept(self, visitor, key):
        visitor.visit_add_tag(self, key)


class LoadResultCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "load_result")

    def accept(self, visitor, key):
        return visitor.visit_load_result(self, key)


class LoadParamCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "load_param")

    def accept(self, visitor, key):
        return visitor.visit_load_param(self, key)


class LoadMetaDataCmd(Command):
    def __init__(self, name, value):
        super().__init__(name, "load_metadata")

    def accept(self, visitor, key):
        return visitor.visit_load_metadata(self, key)


class ShutDownCmd(Command):
    def __init__(self, name="", value=""):
        super().__init__("shutdown", "shutdown")

    def accept(self, visitor, key):  # key is unused here
        return visitor.visit_shutdown()


class DumpCmd(Command):
    def __init__(self, name="", value=""):
        super().__init__("dump", "dump")

    def accept(self, visitor, key):  # key is unused here
        return visitor.visit_dump()
