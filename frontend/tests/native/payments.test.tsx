import React from "react";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react-native";
import { router } from "expo-router";
import "../../src/i18n";
import i18n from "../../src/i18n";
import { usePaymentsUiEnabled } from "../../src/lib/flags";
import { getPaymentProvider } from "../../src/payments";
import PaywallScreen from "../../src/features/payments/PaywallScreen";
import SubscriptionScreen from "../../src/features/payments/SubscriptionScreen";
import { ErrorNotice } from "../../src/design/components";
import { Generated } from "../../src/features/shared/Blocks";
import { useSnackbar } from "../../src/design/components/snackbar-store";

jest.mock("../../src/lib/flags", () => ({
  usePaymentsUiEnabled: jest.fn(),
  useFlags: () => ({ dayScoreNumbers: true }),
}));

jest.mock("../../src/api/hooks", () => {
  const me = { data: { entitlements: {} } };
  return {
    useMe: () => me,
    useConfig: () => ({ data: undefined }),
  };
});

jest.mock("../../src/api/client", () => ({
  accessToken: () => "test-token",
  apiBase: "https://api.test",
}));

const paymentsEnabled = jest.mocked(usePaymentsUiEnabled);
const fetchMock = jest.fn();
global.fetch = fetchMock as unknown as typeof fetch;

beforeEach(async () => {
  await i18n.changeLanguage("en");
  paymentsEnabled.mockReturnValue(true);
  fetchMock.mockReset();
  jest.mocked(router.back).mockClear();
  jest.mocked(router.push).mockClear();
  useSnackbar.setState({ current: null });
});

afterEach(() => {
  jest.clearAllMocks();
});

test("fake provider lists products, purchases, and restores ownership", async () => {
  const provider = getPaymentProvider("fake");
  const products = await provider.getProducts(["app.premium.monthly", ""]);

  expect(products).toEqual([
    expect.objectContaining({
      productId: "app.premium.monthly",
      planId: "premium",
      priceString: null,
    }),
  ]);

  const purchase = await provider.purchase("app.premium.monthly");
  expect(purchase.productId).toBe("app.premium.monthly");
  await expect(provider.restore()).resolves.toEqual([purchase]);
});

test("paywall displays fake products and completes a purchase", async () => {
  const provider = getPaymentProvider("fake");
  jest.spyOn(provider, "getProducts").mockResolvedValue([
    {
      productId: "app.premium.monthly",
      planId: "premium",
      priceString: "$4.99",
      currencyCode: "USD",
      title: "Premium Monthly",
    },
  ]);
  const purchase = jest.spyOn(provider, "purchase");

  await render(<PaywallScreen />);

  expect(await screen.findByText("PREMIUM MONTHLY")).toBeOnTheScreen();
  expect(screen.getByText("$4.99")).toBeOnTheScreen();
  fireEvent.press(screen.getByRole("button", { name: "Subscribe" }));

  await waitFor(() =>
    expect(purchase).toHaveBeenCalledWith("app.premium.monthly"),
  );
  expect(router.back).toHaveBeenCalled();
});

test("paywall handles empty products and the disabled flag", async () => {
  const provider = getPaymentProvider("fake");
  jest.spyOn(provider, "getProducts").mockResolvedValue([]);
  const view = await render(<PaywallScreen />);

  expect(
    await screen.findByText(
      "No products configured yet. Add store product ids in config/plans.json.",
    ),
  ).toBeOnTheScreen();

  paymentsEnabled.mockReturnValue(false);
  await view.rerender(<PaywallScreen />);
  expect(screen.getByText("Payments UI is turned off.")).toBeOnTheScreen();
});

test("subscription displays status and restores through the fake provider", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    json: async () => ({
      plan_id: "premium",
      free_launch: false,
      entitlements: { all: true },
      subscription: {
        plan_id: "premium",
        status: "active",
        expires_at: "2027-01-01T00:00:00Z",
        source_store: "app_store",
        original_transaction_id: "txn-1",
        product_id: "app.premium.monthly",
      },
    }),
  });
  const provider = getPaymentProvider("fake");
  const restored = {
    productId: "app.premium.monthly",
    originalTransactionId: "txn-1",
    expiresAt: "2027-01-01T00:00:00Z",
  };
  jest.spyOn(provider, "restore").mockResolvedValue([restored]);

  await render(<SubscriptionScreen />);

  expect(await screen.findByText("premium")).toBeOnTheScreen();
  expect(screen.getByText("active")).toBeOnTheScreen();
  fireEvent.press(screen.getByRole("button", { name: "Restore purchases" }));

  await waitFor(() =>
    expect(useSnackbar.getState().current?.message).toBe(
      "Purchases restored.",
    ),
  );
  expect(fetchMock).toHaveBeenCalled();
});

test("subscription does not load status while payments UI is disabled", async () => {
  paymentsEnabled.mockReturnValue(false);
  await render(<SubscriptionScreen />);

  expect(screen.getByText("Payments UI is turned off.")).toBeOnTheScreen();
  expect(fetchMock).not.toHaveBeenCalled();
});

test("premium errors render a clear lock in direct and generated paths", async () => {
  const premiumError = { code: "premium_required" };
  const direct = await render(<ErrorNotice error={premiumError} />);
  expect(screen.getByText("🔒 PREMIUM FEATURE")).toBeOnTheScreen();
  expect(
    screen.getByText("This feature needs an active Premium subscription."),
  ).toBeOnTheScreen();
  direct.unmount();

  await render(
    <Generated
      part={{ status: "failed", error: premiumError } as never}
      retry={jest.fn()}
    >
      {() => null}
    </Generated>,
  );
  expect(screen.getByText("🔒 PREMIUM FEATURE")).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: "Premium" })).toBeOnTheScreen();
});
