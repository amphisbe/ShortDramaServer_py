from app.core.config import get_settings
from app.db.database import initialize_runtime
from app.services.user_service import save_progress
from app.models import User, Drama, DramaEpisode

# 初始化内存数据库和表结构
initialize_runtime(create_schema=True, seed=False)

# 创建测试数据
user = User.create(external_user_id="test_user_1", nickname="Test User")
drama = Drama.create(external_drama_id="test_drama_1", title="Test Drama", author_user=user)
episode = DramaEpisode.create(drama=drama, external_video_id="test_video_1", episode_no=1, title="Ep 1", play_url="http://test")

# 测试保存进度
result = save_progress("test_user_1", "test_video_1", 120, False)
print("Save progress result:", result)
