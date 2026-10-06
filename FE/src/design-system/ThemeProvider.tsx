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
const ThemeContext = createContext<ThemeValue>({ name: "night", colors: themes.night, setTheme: () => {} });
export function ThemeProvider({
  children,
  initialTheme = "night",
  theme,
}: PropsWithChildren<{ initialTheme?: ThemeName; theme?: ThemeName }>) {
  const [selected, setTheme] = useState<ThemeName>(initialTheme);
  const name = theme ?? selected;
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
  return value;
}
