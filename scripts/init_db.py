from app.db.database import close_database, initialize_runtime


if __name__ == "__main__":
    try:
        initialize_runtime(create_schema=True, seed=True)
        print("短剧 Demo 数据库初始化完成。")
    finally:
        close_database()
