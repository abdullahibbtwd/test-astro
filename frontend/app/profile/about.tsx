import AccountScreen from "../../src/features/account/AccountScreen";
export default function Page() {
  return <AccountScreen page="about" />;
}

export { RouteError as ErrorBoundary } from "../../src/design/components/RouteError";
