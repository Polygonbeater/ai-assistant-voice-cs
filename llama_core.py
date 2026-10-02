class Schema:
    def __init__(self, name, description, tools):
        self.name = name
        self.description = description
        self.tools = tools

class LlamaModule:
    def __init__(self, schema, execute_function):
        self.schema = schema
        self.execute_function = execute_function

class LlamaModuleManager:
    def __init__(self):
        self.modules = []

    def register_module(self, module):
        self.modules.append(module)

    def get_modules(self):
        return self.modules
