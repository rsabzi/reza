import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskInbox } from "../components/TaskInbox";

function Harness() {
  const [tasks, setTasks] = useState([]);
  return (
    <TaskInbox
      tasks={tasks}
      onCreated={(task) => setTasks((items) => [task, ...items])}
    />
  );
}

test("submitting a task calls the API and shows the returned task without reload", async () => {
  const created = {
    id: 42,
    title: "پروپوزال پروژه جدید",
    description: "نسخه حرفه‌ای",
    status: "pending",
    module_name: null,
  };
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    status: 201,
    json: async () => created,
  });
  const user = userEvent.setup();
  render(<Harness />);

  await user.type(screen.getByLabelText("عنوان تسک"), created.title);
  await user.type(screen.getByLabelText("توضیحات تسک"), created.description);
  await user.click(screen.getByRole("button", { name: /افزودن به همراه/ }));

  await waitFor(() =>
    expect(screen.getByText(created.title)).toBeInTheDocument(),
  );
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/tasks");
  expect(options.method).toBe("POST");
  expect(JSON.parse(options.body)).toEqual({
    title: created.title,
    description: created.description,
    module_name: null,
  });
});

test("task inbox handles its empty state", () => {
  render(<TaskInbox tasks={[]} />);
  expect(screen.getByText("هنوز کاری ثبت نشده")).toBeInTheDocument();
});
