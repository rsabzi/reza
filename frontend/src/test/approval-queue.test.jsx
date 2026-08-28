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
