__all__ = ["process_video_json"]


def __getattr__(name: str):
	if name == "process_video_json":
		from .processor import process_video_json

		return process_video_json
	raise AttributeError(f"module 'nlp_processor' has no attribute {name!r}")
