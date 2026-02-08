let isSessionActive = false;

// Global function for closing modal (accessed by HTML onclick)
function closeSummaryModal() {
  const modal = document.getElementById('session-summary-modal');
  if (modal) {
    modal.style.display = 'none';
  }
}

// Global helpers for modal actions (called from inline HTML buttons)
window.summaryContinue = function() {
  // Close modal then attempt to start a new session by triggering the start button
  closeSummaryModal();
  // Prefer direct call to exposed startTimer if available
  if (typeof window.startTimer === 'function') {
    try { window.startTimer(); return; } catch (e) { /* fallback */ }
  }
  const startBtn = document.getElementById('start-btn');
  if (startBtn) {
    startBtn.disabled = false;
    startBtn.click();
  }
};

window.summaryNewSession = function() {
  // Close modal then trigger reset -> start flow via UI buttons
  closeSummaryModal();
  // Prefer direct reset/start if wrappers available
  if (typeof window.resetTimer === 'function') {
    try { window.resetTimer(); } catch (e) { /* ignore */ }
  } else {
    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) resetBtn.click();
  }

  setTimeout(() => {
    if (typeof window.startTimer === 'function') {
      try { window.startTimer(); return; } catch (e) { /* fallback */ }
    }
    const startBtn = document.getElementById('start-btn');
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.click();
    }
  }, 300);
};

document.addEventListener("DOMContentLoaded", function () {
  const path = window.location.pathname;
  if (path.includes("index.html")) {
    setupLoginPage();
  } else if (path.includes("dashboard.html") || path === "/" || path.includes("dashboard")) {
    setupDashboardPage();
  }
});

// ==================== LOGIN PAGE SETUP ====================
function setupLoginPage() {
  const loginBtn = document.getElementById("loginBtn");
  const signupBtn = document.getElementById("signupBtn");
  const form = document.getElementById("form");

  if (!loginBtn || !signupBtn || !form) {
    console.error("Login form elements not found");
    return;
  }

  // Common function to send data
  function sendAuthRequest(action) {
    const fd = {
      username: form.username.value,
      password: form.password.value,
    };

    fetch(`http://127.0.0.1:5000/${action}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(fd),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "success") {
          console.log(data);
          localStorage.setItem("username", fd.username);
          window.location.href = "dashboard.html";
        } else {
          document.getElementById("message").innerText = data.message;
        }
      })
      .catch((err) => {
        console.error(`${action} failed:`, err);
        document.getElementById("message").innerText =
          "Failed to connect to the server.";
      });
  }

  // Attach events
  loginBtn.addEventListener("click", () => sendAuthRequest("login"));
  signupBtn.addEventListener("click", () => sendAuthRequest("signup"));
}

// ==================== DASHBOARD PAGE SETUP ====================
function setupDashboardPage() {
  // Get all required elements with correct IDs
  const timerDisplay = document.getElementById("timer");
  const statusDisplay = document.getElementById("status");
  const focusScoreDisplay = document.getElementById("focus-score");
  const videoElement = document.getElementById("video-feed");
  const alertBanner = document.getElementById('alert-banner');
  const alertTextEl = document.getElementById('alert-text');
  const alertCloseBtn = document.getElementById('alert-close');
  if (alertCloseBtn) alertCloseBtn.onclick = () => { if (alertBanner) alertBanner.style.display = 'none'; };

  // FIXED: Corrected button IDs to match dashboard.html
  const startBtn = document.getElementById("start-btn");
  const stopBtn = document.getElementById("stop-btn");
  const resetBtn = document.getElementById("reset-btn");

  // Verify all elements exist
  if (!startBtn || !stopBtn || !resetBtn) {
    console.error("Button elements not found. Check IDs match dashboard.html");
    return;
  }

  let totalSeconds = 0;
  let sessionStartTime = null;
  let countdown = null;

  // ==================== TIMER FUNCTIONS ====================
  function formatTime(seconds) {
    const mins = String(Math.floor(seconds / 60)).padStart(2, "0");
    const secs = String(seconds % 60).padStart(2, "0");
    return `${mins}:${secs}`;
  }

  function updateTimerDisplay() {
    if (timerDisplay) {
      timerDisplay.textContent = formatTime(totalSeconds);
    }
  }

  // ==================== FETCH DURATION ====================
  async function fetchDuration() {
    const username = localStorage.getItem("username") || "default_user";
    try {
      const today = new Date().toISOString().split("T")[0];
      const response = await fetch(`${window.location.origin}/duration`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username, date: today }),
      });
      const data = await response.json();
      return data.duration || 25;
    } catch (error) {
      console.error("Failed to fetch session duration:", error);
      return 25;
    }
  }

  // ==================== FOCUS DETECTION ====================
  function startFocusDetection() {
    if (videoElement) {
      console.log('Starting video feed from:', window.location.origin + '/video_feed');
      // Use the same origin the page was served from to avoid cross-origin/mixed-host issues
      videoElement.src = `${window.location.origin}/video_feed?t=${Date.now()}`;
      // Force reload of the image stream
      videoElement.onload = () => { console.log('✓ Video feed loaded'); };
      videoElement.onerror = () => { console.error('✗ Failed to load video feed'); };
    }

    // Start polling using dashboard.html's pollFocusScore function if available,
    // which has sophisticated alert tracking.
    if (typeof window.pollFocusScore === 'function') {
      // Use dashboard.html's polling with alert logic
      const focusScoreInterval = setInterval(() => {
        window.pollFocusScore();
      }, 1000);
      window.focusScoreInterval = focusScoreInterval;
    } else {
      // Fallback: simple polling
      const focusScoreInterval = setInterval(async () => {
        try {
          const response = await fetch(`${window.location.origin}/get_focus_score`);
          const data = await response.json();

          if (focusScoreDisplay) {
            focusScoreDisplay.textContent = `${(data.focus_score * 100).toFixed(1)}%`;
          }

          if (statusDisplay) {
            if (data.focus_score > 0.7) {
              statusDisplay.textContent = "Focused ✅";
              statusDisplay.style.color = "#2e7d32";
            } else if (data.focus_score > 0.3) {
              statusDisplay.textContent = "Partially Focused ⚠️";
              statusDisplay.style.color = "#f59e0b";
            } else {
              statusDisplay.textContent = "Not Focused ❌";
              statusDisplay.style.color = "#e74c3c";
            }
          }
          // NOTE: Alert banner is controlled by dashboard.html's pollFocusScore, not here
        } catch (error) {
          console.error("Error fetching focus score:", error);
        }
      }, 1000);
      window.focusScoreInterval = focusScoreInterval;
    }
  }

  function stopFocusDetection() {
    if (window.focusScoreInterval) {
      clearInterval(window.focusScoreInterval);
    }
    if (videoElement) {
      videoElement.src = "";
    }
    if (focusScoreDisplay) {
      focusScoreDisplay.textContent = "-";
    }
    if (statusDisplay) {
      statusDisplay.textContent = "-";
      statusDisplay.style.color = "";
    }
  }

  // ==================== TIMER CONTROL ====================
  async function startTimer() {
    if (isSessionActive) return;
    // Also check global window.sessionActive from dashboard.html
    if (window.sessionActive === true) return;

    isSessionActive = true;
    window.sessionActive = true;
    
    // Reset alert counters for new session
    window.alertsSent = 0;
    window.secondsUnfocusedSinceLastAlert = 0;
    window.firstAlertArmed = true;
    
    console.log("Session started. sessionActive =", window.sessionActive);

    startBtn.disabled = true;
    stopBtn.disabled = false;
    resetBtn.disabled = true;
    startBtn.innerText = "Running...";

    startFocusDetection();

    try {
      await fetch(`${window.location.origin}/start_session`);
      const minutes = await fetchDuration();
      totalSeconds = minutes * 60;
      updateTimerDisplay();
      sessionStartTime = new Date();

      countdown = setInterval(() => {
        totalSeconds--;
        updateTimerDisplay();
        if (totalSeconds <= 0) {
          clearInterval(countdown);
          stopTimer(true);
        }
      }, 1000);
    } catch (error) {
      console.error("Failed to start session:", error);
      resetState();
    }
  }

  async function stopTimer(autoEnded = false) {
    if (!isSessionActive) return;

    isSessionActive = false;
    window.sessionActive = false;

    if (countdown) {
      clearInterval(countdown);
      countdown = null;
    }

    stopFocusDetection();

    let sessionResults = {};
    try {
      sessionResults = await fetch(`${window.location.origin}/stop_session`).then((res) => res.json());

      const now = new Date();
      const durationCompleted = Math.floor(
        (now - sessionStartTime) / 1000 / 60
      );
      const username = localStorage.getItem("username");

      const payload = {
        username: username,
        session_number: 1,
        duration_completed: durationCompleted,
        date: new Date().toISOString().split("T")[0],
        focus_score: sessionResults.average_focus_score,
        focus_percentage: sessionResults.focus_percentage,
      };

      console.log("Saving session data:", payload);
      await fetch(`${window.location.origin}/save-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      console.error("Failed to stop session or save data:", error);
    } finally {
      stopBtn.innerText = autoEnded ? "Complete" : "Stopped";

      setTimeout(() => {
        resetState();
        stopBtn.innerText = "STOP";
      }, 1500);

      // Show session summary modal with the data
      showSessionSummary(sessionResults);
    }
  }

  async function resetTimer() {
    if (isSessionActive) {
      await stopTimer(false);
    }

    // Reset timer
    const minutes = await fetchDuration();
    totalSeconds = minutes * 60;
    updateTimerDisplay();

    // Reset session state
    resetState();

    // Reset focus display
    if (focusScoreDisplay) {
      focusScoreDisplay.textContent = "-";
    }
    if (statusDisplay) {
      statusDisplay.textContent = "-";
      statusDisplay.style.color = "";
    }

    // Reset video feed
    if (videoElement) {
      videoElement.src = "";
    }

    // Reset detector state
    try {
      await fetch(`${window.location.origin}/start_session`);
    } catch (error) {
      console.error("Reset error:", error);
    }
  }

  function resetState() {
    isSessionActive = false;
    window.sessionActive = false;
    startBtn.disabled = false;
    stopBtn.disabled = true;
    resetBtn.disabled = false;
    startBtn.innerText = "START";
    stopBtn.innerText = "STOP";
  }

  // ==================== SESSION SUMMARY ====================
  function showSessionSummary(data) {
    // Format time helper
    function formatTimeDetail(seconds) {
      if (seconds >= 60) {
        return (seconds / 60).toFixed(1) + ' min';
      }
      return seconds.toFixed(1) + ' s';
    }

    // Get or calculate values
    const sessionDuration = data.session_duration || data.total_session_time || 0;
    const focusedTime = data.total_focus_time || 0;
    const avgFocusScore = data.average_focus_score || 0;
    const focusPercentage = data.focus_percentage || 0;

    // Update modal values
    const summaryTime = document.getElementById('summary-session-time');
    const summaryFocused = document.getElementById('summary-focused-time');
    const summaryScore = document.getElementById('summary-focus-score');
    const summaryPercent = document.getElementById('summary-focus-percentage');
    const summaryFeedback = document.getElementById('summary-feedback');

    if (summaryTime) summaryTime.textContent = formatTimeDetail(sessionDuration);
    if (summaryFocused) summaryFocused.textContent = formatTimeDetail(focusedTime);

    // Average focus score: if value is in [0,1] show as decimal (e.g. 0.31),
    // otherwise treat as ratio and show percent.
    if (summaryScore) {
      if (avgFocusScore !== null && avgFocusScore !== undefined) {
        if (avgFocusScore <= 1) {
          summaryScore.textContent = avgFocusScore.toFixed(2);
        } else {
          summaryScore.textContent = (avgFocusScore * 100).toFixed(1) + '%';
        }
      } else {
        summaryScore.textContent = '0.00';
      }
    }

    // Compute focus percentage if backend didn't supply it
    let computedFocusPercentage = focusPercentage;
    if ((!computedFocusPercentage || computedFocusPercentage === 0) && sessionDuration > 0) {
      computedFocusPercentage = (focusedTime / sessionDuration) * 100;
    }
    if (summaryPercent) summaryPercent.textContent = (computedFocusPercentage || 0).toFixed(1) + '%';

    // Dynamic feedback based on performance
    let feedback = 'Great effort! Keep building your focus habits.';
    if (focusPercentage >= 70) {
      feedback = '⭐ Excellent! You maintained great focus throughout your session!';
    } else if (focusPercentage >= 50) {
      feedback = '👍 Good work! You stayed focused for most of the session.';
    } else if (focusPercentage >= 30) {
      feedback = '💪 Nice try! Focus takes practice. Keep improving!';
    } else {
      feedback = '🏋️ Room for improvement. Remove distractions and try again!';
    }

    if (summaryFeedback) {
      summaryFeedback.textContent = feedback;
    }

    // Show modal
    const modal = document.getElementById('session-summary-modal');
    if (modal) {
      modal.style.display = 'flex';
    }
  }

  // ==================== EVENT LISTENERS ====================
  startBtn.addEventListener("click", startTimer);
  stopBtn.addEventListener("click", () => stopTimer(false));
  resetBtn.addEventListener("click", resetTimer);

  // Expose timer controls to global scope so modal handlers can call them directly
  window.startTimer = startTimer;
  window.stopTimer = stopTimer;
  window.resetTimer = resetTimer;

  // NOTE: demo/sample button removed — summary will display real backend results

  // Initialize on page load
  window.addEventListener("load", async () => {
    // Ensure dashboard.html's global sessionActive is false on load
    if (typeof window.sessionActive === 'undefined') {
      window.sessionActive = false;
    } else {
      window.sessionActive = false;
    }
    
    // Reset script.js state
    isSessionActive = false;
    
    const minutes = await fetchDuration();
    totalSeconds = minutes * 60;
    updateTimerDisplay();
    // Set initial button state: START enabled, STOP/RESET disabled
    startBtn.disabled = false;
    stopBtn.disabled = true;
    resetBtn.disabled = false;
  });
}
