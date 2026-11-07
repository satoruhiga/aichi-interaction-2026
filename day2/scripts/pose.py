"""Body landmarks with visibility; positions use bottom-left UV coordinates."""
import mediapipe as mp
from common.models import ensure_model
from day2.scripts.runtime import arguments, landmarks, run


def serialize(result):
    return {'poses': [dict(landmarks=landmarks(points, visibility=True)) for points in result.pose_landmarks]}


if __name__ == '__main__':
    args = arguments(__doc__)
    model = ensure_model(
        url='https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task',
        path='pose_landmarker_full.task',
        sha256='5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1',
    )
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1)
    try:
        run(args, mp.tasks.vision.PoseLandmarker.create_from_options(options), 'pose_landmarks', serialize)
    except KeyboardInterrupt:
        pass
