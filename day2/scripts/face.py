"""Face landmarks and blendshapes; positions use bottom-left UV coordinates."""
import mediapipe as mp
from day2.scripts.runtime import MODELS, arguments, landmarks, run


def serialize(result):
    return {'faces': [dict(landmarks=landmarks(points),
                          blendshapes={c.category_name: c.score for c in result.face_blendshapes[i]})
                      for i, points in enumerate(result.face_landmarks)]}


if __name__ == '__main__':
    args = arguments(__doc__)
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODELS / 'face_landmarker.task')),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1, output_face_blendshapes=True)
    try:
        run(args, mp.tasks.vision.FaceLandmarker.create_from_options(options), 'face_landmarks', serialize)
    except KeyboardInterrupt:
        pass
