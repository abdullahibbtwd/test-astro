import AccountScreen from "../../src/features/account/AccountScreen";
export default function Page() {
  return <AccountScreen page="settings" />;
}

export { RouteError as ErrorBoundary } from "../../src/design/components/RouteError";
