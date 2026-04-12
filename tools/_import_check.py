import importlib, traceback
try:
    importlib.import_module('app.menu.routes')
    print('import ok')
except Exception:
    traceback.print_exc()
