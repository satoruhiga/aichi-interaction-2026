"""Hand landmarks for up to four hands; positions use bottom-left UV coordinates."""
import mediapipe as mp
from common.models import ensure_model
from day2.scripts.runtime import arguments, landmarks, run


def serialize(result):
    return {'hands': [dict(landmarks=landmarks(points),
                          handedness=result.handedness[i][0].category_name,
                          score=result.handedness[i][0].score)
                      for i, points in enumerate(result.hand_landmarks)]}


if __name__ == '__main__':
    args = arguments(__doc__)
    model = ensure_model(
        url='https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
        path='hand_landmarker.task',
        sha256='fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1',
    )
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=4)
    try:
        run(args, mp.tasks.vision.HandLandmarker.create_from_options(options), 'hand_landmarks', serialize)
    except KeyboardInterrupt:
        pass
