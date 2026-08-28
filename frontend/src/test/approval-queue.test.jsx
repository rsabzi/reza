import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApprovalQueue } from "../components/ApprovalQueue";

const waitingStep = {
  id: 7,
  task_id: 3,
  title: "ارسال پیام معرفی",
  status: "needs_approval",
  tool_name: "generate_outreach_script",
  arguments: { salon_id: 9 },
};

function Harness() {
  const [steps, setSteps] = useState([waitingStep]);
  return (
    <ApprovalQueue
      steps={steps}
      onApproved={(step) =>
        setSteps((items) => items.filter((item) => item.id !== step.id))
      }
    />
  );
}

test("Approve calls endpoint and updates queue without a full reload", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      id: 3,
      title: "Campaign",
      status: "done",
      steps: [{ ...waitingStep, status: "done" }],
    }),
  });
  const user = userEvent.setup();
  render(<Harness />);
  expect(screen.getByText(waitingStep.title)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /تأیید و ادامه/ }));
  await waitFor(() =>
    expect(screen.getByText("صف تأیید خالی است")).toBeInTheDocument(),
  );
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/steps/7/approve",
    expect.objectContaining({ method: "POST" }),
  );
});

test("approval queue handles empty state", () => {
  render(<ApprovalQueue steps={[]} />);
  expect(screen.getByText("صف تأیید خالی است")).toBeInTheDocument();
});

test("Approving an action immediately shows its output with a copy button", async () => {
  const now = new Date().toISOString();
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      id: 3,
      title: "Campaign",
      status: "done",
      steps: [
        {
          ...waitingStep,
          status: "done",
          updated_at: now,
          result: {
            salon_id: 9,
            script: "سلام سالن نگین عزیز، پیشنهاد همکاری داریم.",
          },
        },
      ],
    }),
  });
  const user = userEvent.setup();
  render(<Harness />);

  await user.click(screen.getByRole("button", { name: /تأیید و ادامه/ }));

  const dialog = await screen.findByTestId("approval-result");
  expect(dialog).toBeInTheDocument();
  expect(screen.getByTestId("approval-result-text")).toHaveTextContent(
    "سلام سالن نگین عزیز",
  );
  expect(screen.getByRole("button", { name: /کپی خروجی/ })).toBeInTheDocument();

  // Closing the result dialog returns to the (now empty) queue.
  await user.click(screen.getAllByRole("button", { name: "بستن" }).at(-1));
  await waitFor(() =>
    expect(screen.getByText("صف تأیید خالی است")).toBeInTheDocument(),
  );
});

test("Approval failure surfaces the step error in the result dialog", async () => {
  const now = new Date().toISOString();
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      id: 3,
      title: "Campaign",
      status: "failed",
      steps: [
        {
          ...waitingStep,
          status: "failed",
          updated_at: now,
          result: null,
          error: "سالن مورد نظر یافت نشد",
        },
      ],
    }),
  });
  const user = userEvent.setup();
  render(<Harness />);

  await user.click(screen.getByRole("button", { name: /تأیید و ادامه/ }));

  const dialog = await screen.findByTestId("approval-result");
  expect(dialog).toHaveTextContent("سالن مورد نظر یافت نشد");
});
