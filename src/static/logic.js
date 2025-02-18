  // Handle collapsible sections
  document.querySelectorAll('.section-header').forEach(header => {
    header.addEventListener('click', () => {
      const content = header.nextElementSibling;
      const arrow = header.querySelector('.arrow');

      content.classList.toggle('hidden');
      arrow.classList.toggle('collapsed');
    });
  });

  // Copy code buttons
  async function copyCode(elementId) {
    const codeElement = document.getElementById(elementId);
    const button = codeElement.parentElement.querySelector('.copy-button');

    try {
      await navigator.clipboard.writeText(codeElement.textContent.trim());

      // Visual feedback
      button.classList.add('copied');

      // Reset after 2 seconds
      setTimeout(() => {
        button.classList.remove('copied');
      }, 2500);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }

  // Load submissions
  async function loadSubmissions() {
    const resp = await fetch("/submissions");
    const data = await resp.json();

    const tbody = document.querySelector("#submissionsTable tbody");
    tbody.innerHTML = "";

    data.forEach(entry => {
      const row = document.createElement("tr");

      const timeCell = document.createElement("td");
      timeCell.textContent = entry.time;
      row.appendChild(timeCell);

      const idCell = document.createElement("td");
      idCell.textContent = entry.submission_name;
      row.appendChild(idCell);

      const sigCell = document.createElement("td");
      sigCell.textContent = entry.signature;
      row.appendChild(sigCell);

      tbody.appendChild(row);
    });
  }

  let toggle_loop_load = false;
  function loopLoadSubmissions() {
    if (toggle_loop_load) {
      clearInterval(interval);
      toggle_loop_load = false;
      // change button color
      const successBanner = document.querySelector("#loopLoadSubmissions");
      successBanner.style.backgroundColor = "rgba(12, 49, 74, 1)";
    } else {
      interval = setInterval(loadSubmissions, 2000);
      toggle_loop_load = true;
      // change button id=loopLoadSubmissions color
      const successBanner = document.querySelector("#loopLoadSubmissions");
      successBanner.style.backgroundColor = "rgb(38, 93, 133)";
    }
  }

  // Hide success banner
  function hideBanner() {
    const successBanner = document.querySelector(".success-banner");
    successBanner.style.display = "none";
  }

  // Adding check submission button functionality
  document.getElementById("checkButton").addEventListener("click", async () => {
    const content = document.getElementById("content").value;
    const response = await fetch("/check-submission-ui", {
      method: "POST",
      headers: {"Content-Type": "application/x-www-form-urlencoded"},
      body: new URLSearchParams({content}),
    });
    const result = await response.json();
    const issuesDiv = document.getElementById("validation-issues");

    if (!response.ok) {
      alert("Error: " + response.status + " " + result.detail);
      return;
    }

    if (result.status === "issues found") {
      issuesDiv.innerHTML = "<b>Validation issues detected:</b><br>" + result.issues.join("<br>") +
          "<br><br>Fix the issues to ensure correct scoring of your submission!";
      issuesDiv.style.color = "red";
    } else {
      issuesDiv.textContent = "No validation issues detected. Click submit button to submit!";
      issuesDiv.style.color = "green";
    }
  });

  // Adding submit functionality
  document.getElementById("submitButton").addEventListener("click", async () => {
    const content = document.getElementById("content").value;
    const response_validation = await fetch("/check-submission-ui", {
      method: "POST",
      headers: {"Content-Type": "application/x-www-form-urlencoded"},
      body: new URLSearchParams({content}),
    });
    const result_validation = await response_validation.json();

    if (!response_validation.ok) {
      alert("Error: " + response_validation.status + " " + result_validation.detail);
      return;
    } else {
      if (result_validation.status === "issues found" || !response_validation.ok) {
        const submitAnyway = confirm("These issues could prevent correct scoring of your submission:\n"
            + result_validation.issues.join("")
            + "\n\n\n Please adhere to the submission guidelines to ensure correct scoring."  // TODO add link to guidelines?
            + "\n\n Submit despite possible scoring issues?");
        if (!submitAnyway) {
          return;
        }
      }
      const response = await fetch("/submit-ui", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({content}),
      });
      const result = await response.json();

      if (result.status === "issues found") {
        alert("Successfully submitted with issues!\n\nConsider submitting again adhering to the submission " +
            "guidelines. Use the identical team name and mail address to overwrite this submission. \n\n" +
            "Issues: " + result.issues.join("") + "\n\n" +
            "Team: " + result.response.submission_name + "\n\n" +
            "Signature: " + result.response.signature + "\n\n"
        );
      } else if (result.status === "success") {
        alert("Submission successful!" + "\n\n" +
            "Team: " + result.response.submission_name + "\n\n" +
            "Signature: " + result.response.signature + "\n\n"
        );
      }
      const successBanner = document.querySelector(".success-banner");
      successBanner.style.display = "block";
      const bannerSubmitData = document.querySelector("#submission-data")
      bannerSubmitData.innerHTML = "Team: " + result.response.submission_name + "<br>Signature: " + result.response.signature;
      const bannerSubmitTspData = document.querySelector("#tsp-verification-data")
      bannerSubmitTspData.textContent = JSON.stringify(result.response.tsp_verification_data);

      // scroll to top to show submission success banner
      window.scrollTo(0, 0);
    }
    await loadSubmissions();
  });

  window.addEventListener("DOMContentLoaded", () => {
    loadSubmissions();
  });