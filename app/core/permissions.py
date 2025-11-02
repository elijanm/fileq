permissions_registry = {}

def register_permissions(plugin_name, permissions):
    permissions_registry[plugin_name] = permissions

def get_all_permissions():
    return permissions_registry
