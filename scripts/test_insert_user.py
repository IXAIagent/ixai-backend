from app.core.database import Base, engine, SessionLocal
from app.models.models import User

Base.metadata.create_all(bind=engine)

db = SessionLocal()

user = User(email="demo@yixuan.ai")
db.add(user)
db.commit()

print("User inserted successfully")

db.close()