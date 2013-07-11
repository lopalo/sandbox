from functools import wraps


class ModeError(Exception):
    pass


_debug_mode = False


def set_debug_mode():
    global _debug_mode
    _debug_mode = True


def debug_func(func):
    @wraps(func)
    def new_func(*args, **kwargs):
        if not _debug_mode:
            raise ModeError('Debug function or method is not available')
        return func(*args, **kwargs)
    return new_func
