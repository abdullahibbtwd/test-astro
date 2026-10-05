import {
  createContext,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { themes, type ThemeName, type ThemeColors } from "./theme/tokens";
type ThemeValue = {
  name: ThemeName;
  colors: ThemeColors;
  setTheme: (name: ThemeName) => void;
};
const ThemeContext = createContext<ThemeValue | null>(null);
export function ThemeProvider({
  children,
  initialTheme = "night",
}: PropsWithChildren<{ initialTheme?: ThemeName }>) {
  const [name, setTheme] = useState<ThemeName>(initialTheme);
  const value = useMemo(
    () => ({ name, colors: themes[name], setTheme }),
    [name],
  );
  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}
export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("Design-system components require ThemeProvider");
  return value;
}
