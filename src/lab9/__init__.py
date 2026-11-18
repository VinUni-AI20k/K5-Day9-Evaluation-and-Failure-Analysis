import mimetypes
mimetypes.init = lambda *args, **kwargs: None
mimetypes.inited = True
