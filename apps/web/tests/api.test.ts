import { it, expect, vi } from "vitest";
import { api, displayMoney, transactionSchema } from "@/lib/api";
import { transaction, preview, id } from "./fixtures";
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
it("preserves monetary precision and rejects numeric money", () => {
  expect(displayMoney("9999999999999999.1234", "AED")).toBe(
    "+9,999,999,999,999,999.1234 AED",
  );
  expect(displayMoney("-0.0001", "USD")).toBe("−0.0001 USD");
  expect(displayMoney("-48.5000", "AED")).toBe("−48.50 AED");
  expect(
    transactionSchema.safeParse({ ...transaction, amount: -48.5 }).success,
  ).toBe(false);
});
it("sends fresh CSRF, same-origin cookies and a quoted version on correction", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ csrf_token: "synthetic-token" }))
    .mockResolvedValueOnce(json(transaction));
  await api.category(transaction, "Education");
  expect(fetcher.mock.calls[1][1]).toMatchObject({
    method: "PATCH",
    credentials: "same-origin",
    cache: "no-store",
    headers: { "X-CSRF-Token": "synthetic-token", "If-Match": '"1"' },
    body: '{"category":"Education"}',
  });
});
it("keeps file bytes and retry key, without sending the private filename", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (url) =>
      String(url).endsWith("csrf")
        ? json({ csrf_token: "test" })
        : json(preview),
    );
  const file = new File(["synthetic"], "private-name.csv");
  await api.upload(file, id);
  await api.upload(file, id);
  for (const call of [fetcher.mock.calls[1], fetcher.mock.calls[3]])
    expect(call[1]).toMatchObject({
      body: file,
      headers: {
        "Content-Type": "text/csv",
        "X-Filename": "statement.csv",
        "Idempotency-Key": id,
      },
    });
});
it("hides arbitrary server errors and rejects malformed responses", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      json(
        { error: { code: "INTERNAL_ERROR", message: "secret SQL traceback" } },
        500,
      ),
    )
    .mockResolvedValue(json({ amount: 123 }));
  await expect(api.me()).rejects.toThrow("Check your connection");
  await expect(api.transaction(id)).rejects.toThrow("Check your connection");
});
it("announces expired private requests without blind retries", async () => {
  const listener = vi.fn();
  window.addEventListener("ledgerx:unauthorized", listener);
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(json({ error: { code: "AUTH_REQUIRED" } }, 401));
  await expect(api.transactions()).rejects.toThrow("session has ended");
  expect(listener).toHaveBeenCalledOnce();
  expect(fetcher).toHaveBeenCalledOnce();
  window.removeEventListener("ledgerx:unauthorized", listener);
});
