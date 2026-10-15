import React from "react";
import { render, screen, userEvent } from "@testing-library/react-native";
import { ThemeProvider } from "../../src/design-system/ThemeProvider";
import { AppText } from "../../src/design-system/text/AppText";
import { Button } from "../../src/design-system/components/Button";
import { TraitCard } from "../../src/design-system/components/TraitCard";
import { Field, SelectField } from "../../src/design-system/components/Fields";
test("Turkish display text and disabled buttons retain correct accessible state", async () => {
  const press = jest.fn(),
    user = userEvent.setup();
  await render(
    <ThemeProvider>
      <AppText variant="displayTitle" lang="tr">
        Haritamı oluştur
      </AppText>
      <Button disabled onPress={press} lang="en">
        Generate my chart
      </Button>
    </ThemeProvider>,
  );
  expect(screen.getByText("HARİTAMI OLUŞTUR")).toBeOnTheScreen();
  const button = screen.getByRole("button", { name: "GENERATE MY CHART" });
  expect(button).toBeDisabled();
  await user.press(button);
  expect(press).not.toHaveBeenCalled();
});
test("TraitCard exposes checkbox state and toggles the existing value", async () => {
  const toggle = jest.fn(),
    user = userEvent.setup();
  await render(
    <ThemeProvider>
      <TraitCard
        label="Duygusal denge"
        motif="crescent"
        selected
        onToggle={toggle}
        lang="tr"
      />
    </ThemeProvider>,
  );
  const card = screen.getByRole("checkbox", { name: "Duygusal denge" });
  expect(card).toBeChecked();
  await user.press(card);
  expect(toggle).toHaveBeenCalledWith(false);
});
test("field error replaces hint and disabled picker cannot open", async () => {
  const open = jest.fn(),
    user = userEvent.setup();
  await render(
    <ThemeProvider initialTheme="parchment">
      <Field label="Birthplace" error="Choose a place" hint="Hidden hint">
        <SelectField
          disabled
          accessibilityLabel="Birthplace picker"
          placeholder="Choose"
          onPress={open}
        />
      </Field>
    </ThemeProvider>,
  );
  expect(screen.getByText("Choose a place")).toBeOnTheScreen();
  expect(screen.queryByText("Hidden hint")).toBeNull();
  await user.press(screen.getByRole("button", { name: "Birthplace picker" }));
  expect(open).not.toHaveBeenCalled();
});
