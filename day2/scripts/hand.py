"""Hand landmarks for up to four hands; positions use bottom-left UV coordinates."""
import mediapipe as mp
from day2.scripts.runtime import MODELS, arguments, landmarks, run


def serialize(result):
    return {'hands': [dict(landmarks=landmarks(points),
                          handedness=result.handedness[i][0].category_name,
                          score=result.handedness[i][0].score)
                      for i, points in enumerate(result.hand_landmarks)]}


if __name__ == '__main__':
    args = arguments(__doc__)
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODELS / 'hand_landmarker.task')),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=4)
    try:
        run(args, mp.tasks.vision.HandLandmarker.create_from_options(options), 'hand_landmarks', serialize)
    except KeyboardInterrupt:
        pass
