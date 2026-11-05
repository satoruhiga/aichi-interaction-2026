"""Convert the face selected by the upstream JSON DAT to the preview table."""

import json
from itertools import zip_longest


def face_rows(face, aspect):
    rows = [["tx0", "ty0", "tz0", "blendshape:labels0", "blendshape:scores0"]]
    if not face:
        return rows

    landmarks = face.get("landmarks", [])
    blendshapes = face.get("blendshapes", {}).items()
    for point, blendshape in zip_longest(landmarks, blendshapes):
        position = ["", "", ""]
        if point is not None:
            # The existing orthographic preview uses image width as one unit.
            position = [point["x"], point["y"] * aspect, 0]
        label, score = blendshape if blendshape is not None else ("", "")
        rows.append(position + [label, score])
    return rows


def onCook(scriptOp):
    face = json.loads(scriptOp.inputs[0].text or "null")
    video = op("/project1/VIDEO")
    rows = face_rows(face, video.height / video.width)
    scriptOp.clear()
    for row in rows:
        scriptOp.appendRow(row)
