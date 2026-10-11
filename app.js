const form = document.querySelector("#todo-form");
const input = document.querySelector("#todo-input");
const list = document.querySelector("#todo-list");
const count = document.querySelector("#task-count");
const emptyState = document.querySelector("#empty-state");
const emptyMessage = document.querySelector("#empty-message");
const errorMessage = document.querySelector("#error-message");
const filterButtons = [...document.querySelectorAll(".filter-button")];

let todos = [];
let activeFilter = "all";

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "Something went wrong. Please try again.");
  }

  return response.status === 204 ? null : response.json();
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = !message;
}

function render() {
  const visibleTodos = todos.filter((todo) => {
    if (activeFilter === "active") return !todo.completed;
    if (activeFilter === "completed") return todo.completed;
    return true;
  });
  const remaining = todos.filter((todo) => !todo.completed).length;

  count.textContent = `${remaining} ${remaining === 1 ? "task" : "tasks"} left`;
  list.replaceChildren();
  emptyState.hidden = visibleTodos.length > 0;
  if (visibleTodos.length === 0) {
    emptyMessage.textContent =
      todos.length === 0
        ? "Your next win starts here. Add a task!"
        : `No ${activeFilter} tasks right now.`;
  }

  for (const todo of visibleTodos) {
    const item = document.createElement("li");
    item.className = `todo-item${todo.completed ? " is-completed" : ""}`;

    const checkbox = document.createElement("button");
    checkbox.className = "todo-checkbox";
    checkbox.type = "button";
    checkbox.setAttribute("aria-label", `${todo.completed ? "Mark as active" : "Mark as completed"}: ${todo.title}`);
    checkbox.setAttribute("aria-pressed", String(todo.completed));
    checkbox.addEventListener("click", () => updateTodo(todo.id, !todo.completed));

    const title = document.createElement("span");
    title.className = "todo-title";
    title.textContent = todo.title;

    const remove = document.createElement("button");
    remove.className = "delete-button";
    remove.type = "button";
    remove.setAttribute("aria-label", `Delete: ${todo.title}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => deleteTodo(todo.id));

    item.append(checkbox, title, remove);
    list.append(item);
  }
}

async function loadTodos() {
  try {
    todos = await request("/api/todos");
    render();
  } catch (error) {
    showError(error.message);
  }
}

async function updateTodo(id, completed) {
  showError("");
  try {
    const updated = await request(`/api/todos/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ completed }),
    });
    todos = todos.map((todo) => (todo.id === id ? updated : todo));
    render();
  } catch (error) {
    showError(error.message);
  }
}

async function deleteTodo(id) {
  showError("");
  try {
    await request(`/api/todos/${id}`, { method: "DELETE" });
    todos = todos.filter((todo) => todo.id !== id);
    render();
  } catch (error) {
    showError(error.message);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = input.value.trim();
  if (!title) return;

  showError("");
  try {
    const todo = await request("/api/todos", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
    todos.unshift(todo);
    input.value = "";
    activeFilter = "all";
    filterButtons.forEach((button) => {
      const isActive = button.dataset.filter === activeFilter;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });
    render();
    input.focus();
  } catch (error) {
    showError(error.message);
  }
});

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    activeFilter = button.dataset.filter;
    filterButtons.forEach((filterButton) => {
      const isActive = filterButton === button;
      filterButton.classList.toggle("is-active", isActive);
      filterButton.setAttribute("aria-pressed", String(isActive));
    });
    render();
  });
});

loadTodos();
