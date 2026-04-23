**Role**: Edge Case Hunter
**Goal**: Focus on I/O boundaries and state limits in douyin_fetcher.py and downloader.py.

**Focus**:
- What happens if the network drops halfway through downloading a 500MB video? 
- Will chunk iteration leave a corrupted orphaned file behind?
- What happens to state if the database is locked?
