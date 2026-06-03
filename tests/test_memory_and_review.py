import asyncio
import sys
import os
from datetime import date
from sqlalchemy import select

# Include server directory in search path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from app.core.database import SessionLocal
from app.models.user import User
from app.services.memory_service import MemoryService
from app.models.student_memory import StudentMemory

async def test_pipeline():
    print("==================================================")
    print("STARTING INTEGRATION TEST FOR MEMORY & DAILY REVIEW")
    print("==================================================")
    
    async with SessionLocal() as db:
        # 1. Fetch the default seeded student
        res = await db.execute(select(User).where(User.username == "student"))
        student = res.scalars().first()
        if not student:
            print("[ERROR] Seeded student user 'student' not found! Make sure to run seeder first.")
            sys.exit(1)
        
        print(f"[OK] Found student user: {student.username} (ID: {student.id})")
        
        # Clean up existing review and memories for a fresh run
        from app.models.student_memory import DailyReview
        from sqlalchemy import delete
        await db.execute(delete(StudentMemory).where(StudentMemory.user_id == student.id))
        await db.execute(delete(DailyReview).where(DailyReview.user_id == student.id))
        await db.commit()
        
        # 2. Trigger Daily Review generation (uses MockProvider under the hood since API key is blank)
        review_date = date.today()
        print(f"[RUN] Generating daily review for date: {review_date}...")
        review = await MemoryService.generate_daily_review(db, student.id, review_date)
        
        print(f"[OK] Review status: {review.status}")
        print(f"[OK] Generated review summary preview:\n{review.summary[:200]}...")
        print(f"[OK] New memory list: {review.new_memories}")
        print(f"[OK] Updated memory list: {review.updated_memories}")
        
        # 3. Retrieve student memories via service
        memories, last_updated = await MemoryService.get_student_memories(db, student.id)
        print(f"[OK] Retreived {len(memories)} active memories:")
        for idx, m in enumerate(memories):
            print(f"  {idx+1}. [{m.memory_type}/{m.category}] {m.content} (Confidence: {m.confidence:.2f})")
            
        # 4. Soft-delete testing
        if len(memories) > 0:
            target_mem = memories[0]
            print(f"[RUN] Testing soft-delete on memory item ID: {target_mem.id}...")
            await MemoryService.delete_student_memory(db, student.id, target_mem.id)
            print("[OK] Soft delete call finished.")
            
            # Verify it is no longer returned as active
            active_mems, _ = await MemoryService.get_student_memories(db, student.id)
            print(f"[OK] Active memories remaining: {len(active_mems)}")
            assert all(m.id != target_mem.id for m in active_mems), "Deleted memory should not be returned as active"
            
            # Verify it still exists in database with status='deleted'
            check_res = await db.execute(select(StudentMemory).where(StudentMemory.id == target_mem.id))
            chk = check_res.scalars().first()
            print(f"[OK] Memory item in DB now has status: {chk.status}")
            assert chk.status == "deleted", "Memory status should be 'deleted' in DB"
            
    print("==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    # Ensure correct working directory context
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    asyncio.run(test_pipeline())
