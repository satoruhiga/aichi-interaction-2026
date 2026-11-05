"""Body landmarks with visibility; positions use bottom-left UV coordinates."""
import mediapipe as mp
from day2.scripts.runtime import MODELS, arguments, landmarks, run


def serialize(result):
    return {'poses': [dict(landmarks=landmarks(points, visibility=True)) for points in result.pose_landmarks]}


if __name__ == '__main__':
    args = arguments(__doc__)
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODELS / 'pose_landmarker_full.task')),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1)
    try:
        run(args, mp.tasks.vision.PoseLandmarker.create_from_options(options), 'pose_landmarks', serialize)
    except KeyboardInterrupt:
        pass
