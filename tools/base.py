class Tool:
    name = "base"
    description = ""
    level = None

    def __init__(self, memory, policies):
        self.memory = memory
        self.policies = policies

    def matches(self, request):
        raise NotImplementedError

    def run(self, request):
        raise NotImplementedError