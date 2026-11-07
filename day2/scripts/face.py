"""Face landmarks and blendshapes; positions use bottom-left UV coordinates."""
import mediapipe as mp
from common.models import ensure_model
from day2.scripts.runtime import arguments, landmarks, run


def serialize(result):
    return {'faces': [dict(landmarks=landmarks(points),
                          blendshapes={c.category_name: c.score for c in result.face_blendshapes[i]})
                      for i, points in enumerate(result.face_landmarks)]}


if __name__ == '__main__':
    args = arguments(__doc__)
    model = ensure_model(
        url='https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task',
        path='face_landmarker.task',
        sha256='64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff',
    )
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1, output_face_blendshapes=True)
    try:
        run(args, mp.tasks.vision.FaceLandmarker.create_from_options(options), 'face_landmarks', serialize)
    except KeyboardInterrupt:
        pass
