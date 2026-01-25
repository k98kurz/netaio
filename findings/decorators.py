class Thing:
    def dec(self, fn):
        stuff = ['Decorated!']
        def inner(*args):
            stuff.append(fn(*args))
            return stuff
        return inner

    def what(self, is_it):
        @self.dec
        def inner(*args):
            return {'len': len(args), 'it': args}
        return inner(is_it)

