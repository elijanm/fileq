from bson import ObjectId

def serialize_doc(doc):
    """Convert ObjectId to str in a Mongo document"""
    if not doc:
        return None
    return {
        k: str(v) if isinstance(v, ObjectId) else v
        for k, v in doc.items()
    }
