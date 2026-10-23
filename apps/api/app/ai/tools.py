from fastapi import HTTPException


def available(db, ctx, lodge_id):
    return []


def execute(name, arguments, db, ctx, lodge_id, request):
    raise HTTPException(422, "AI tool is not registered")
