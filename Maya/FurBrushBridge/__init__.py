"""FurBrush Maya bridge. Run show() inside Maya's Python 3 environment."""

def show():
    from .maya_bridge import show as open_window
    return open_window()
