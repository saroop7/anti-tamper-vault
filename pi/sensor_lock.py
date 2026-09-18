"""One process, one fingerprint sensor -- this lock is held by whichever of
fingerprint_auth.verify_owner() or enrollment_worker's enrollment flow is
currently talking to the R307, so they never open the UART at the same time.
"""
import threading

fingerprint_lock = threading.Lock()
