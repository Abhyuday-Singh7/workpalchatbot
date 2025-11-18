const API_BASE = "http://127.0.0.1:8000";

const state = {
  userId: "",
  departments: [],
};

function showPage(id) {
  document.querySelectorAll(".page").forEach((page) => {
    page.classList.remove("active");
  });
  const el = document.getElementById(id);
  if (el) el.classList.add("active");
}

function renderDepartmentUploads() {
  const container = document.getElementById("departmentUploads");
  container.innerHTML = "";
  state.departments.forEach((dept) => {
    const div = document.createElement("div");
    div.className = "dept-upload";
    div.innerHTML = `
      <h4>${dept}</h4>
      <label>Instruction PDF/TXT:
        <input type="file" data-type="rules" data-dept="${dept}">
      </label>
      <label>Excel Database (.xlsx):
        <input type="file" data-type="excel" data-dept="${dept}">
      </label>
    `;
    container.appendChild(div);
  });
}

document
  .getElementById("nextFromDepartments")
  .addEventListener("click", async (event) => {
    event.preventDefault();
    const status = document.getElementById("page1Status");
    status.textContent = "";

    const userIdInput = document.getElementById("userIdInput");
    const userId = userIdInput.value.trim();
    if (!userId) {
      status.textContent = "Please enter a User ID.";
      return;
    }

    const checked = Array.from(
      document.querySelectorAll("#page1 input[type=checkbox]:checked")
    ).map((el) => el.value);

    if (checked.length === 0) {
      status.textContent = "Please select at least one department.";
      return;
    }

    if (checked.length > 6) {
      status.textContent = "Please select at most 6 departments.";
      return;
    }

    state.userId = userId;
    state.departments = checked;

    try {
      const resp = await fetch(`${API_BASE}/departments/setup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: state.userId,
          departments: state.departments,
        }),
      });
      if (!resp.ok) {
        const error = await resp.text();
        status.textContent = "Error setting up departments: " + error;
        return;
      }
      await resp.json();
      status.textContent = "Departments initialized. Proceed to upload files.";
      renderDepartmentUploads();
      showPage("page2");
    } catch (err) {
      console.error(err);
      status.textContent = "Network error while setting up departments.";
    }
  });

document
  .getElementById("uploadAndContinue")
  .addEventListener("click", async (event) => {
    event.preventDefault();
    const status = document.getElementById("page2Status");
    status.textContent = "Uploading files...";

    try {
      // Department instruction PDFs and Excel databases
      const fileInputs = document.querySelectorAll(
        "#departmentUploads input[type=file]"
      );

      const uploadPromises = [];
      fileInputs.forEach((input) => {
        const file = input.files[0];
        if (!file) return;
        const dept = input.getAttribute("data-dept");
        const type = input.getAttribute("data-type");
        const formData = new FormData();
        formData.append("user_id", state.userId);
        formData.append("department", dept);
        formData.append("file", file);

        if (type === "rules") {
          uploadPromises.push(
            fetch(`${API_BASE}/departments/${encodeURIComponent(dept)}/upload-rules`, {
              method: "POST",
              body: formData,
            })
          );
        } else if (type === "excel") {
          uploadPromises.push(
            fetch(`${API_BASE}/departments/${encodeURIComponent(dept)}/upload-excel`, {
              method: "POST",
              body: formData,
            })
          );
        }
      });

      // Central company rules
      const centralFileInput = document.getElementById("centralRulesFile");
      const centralFile = centralFileInput.files[0];
      if (centralFile) {
        const centralForm = new FormData();
        centralForm.append("user_id", state.userId);
        centralForm.append("file", centralFile);
        uploadPromises.push(
          fetch(`${API_BASE}/central-rules/upload`, {
            method: "POST",
            body: centralForm,
          })
        );
      }

      await Promise.all(uploadPromises);
      status.textContent =
        "Files uploaded successfully. You can now use the central WorkPal bot.";
      // Move to the WorkPal bot page after uploads finish
      showPage("page3");
    } catch (err) {
      console.error(err);
      status.textContent = "Error uploading files. Check console for details.";
    }
  });

function appendChatMessage(role, text) {
  const chatWindow = document.getElementById("chatWindow");
  const div = document.createElement("div");
  div.className = `chat-message ${role}`;
  div.textContent = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

document.getElementById("sendMessage").addEventListener("click", async (event) => {
  event.preventDefault();
  const status = document.getElementById("page3Status");
  status.textContent = "";

  const input = document.getElementById("chatMessageInput");
  const message = input.value.trim();
  if (!message) {
    status.textContent = "Please enter a message.";
    return;
  }

  appendChatMessage("user", `You: ${message}`);
  input.value = "";

  try {
    const resp = await fetch(`${API_BASE}/workpal/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: state.userId,
        message,
        departments: state.departments,
      }),
    });

    if (!resp.ok) {
      const errorText = await resp.text();
      appendChatMessage("system", "Error: " + errorText);
      return;
    }

    const data = await resp.json();
    appendChatMessage("bot", `WorkPal: ${data.reply}`);

    if (data.intent) {
      appendChatMessage(
        "system",
        `INTENT: ACTION=${data.intent.ACTION}, DEPARTMENT=${data.intent.DEPARTMENT}`
      );
    }

    if (data.execution_result) {
      appendChatMessage(
        "system",
        `Execution: ${data.execution_result.message}`
      );
    }
  } catch (err) {
    console.error(err);
    appendChatMessage(
      "system",
      "Network error while calling WorkPal backend."
    );
  }
});
