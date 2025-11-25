class XTDBRouter:
    """A router to control all database operations on models in the auth and contenttypes applications."""

    route_app_labels = {"objects"}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return "xtdb"
        else:
            return "default"

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return "xtdb"
        else:
            return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True  # TODO: use

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Make sure the auth and contenttypes apps only appear in the 'auth_db' database."""
        if app_label in self.route_app_labels:
            return False

        return None
