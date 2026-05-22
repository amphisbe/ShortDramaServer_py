from typing import Any


def save_model(instance: Any, values: dict[str, Any]) -> None:
    """批量设置模型实例属性并保存。"""
    for key, value in values.items():
        setattr(instance, key, value)
    instance.save()
