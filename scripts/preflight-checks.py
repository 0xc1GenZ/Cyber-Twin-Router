import shutil, subprocess, sys
print("🔍 Running pre-flight checks...")
if not shutil.which("docker"):
    print("❌ Docker not found. Install Docker Desktop")
    sys.exit(1)
if not shutil.which("python"):
    print("❌ Python not found. Install from python.org")
    sys.exit(1)
print("✅ All checks passed!")
