import React from "react";
import { render, screen, userEvent } from "@testing-library/react-native";
import "../../src/i18n";
import i18n from "../../src/i18n";
import { Button, Field, Chip } from "../../src/design/components";
import { PlaceSearch } from "../../src/design/components/PlaceSearch";
const place = {
  place_id: "one",
  name: "Alexandria",
  admin1: "Virginia",
  country_name: "United States",
  country_code: "US",
  lat: 38,
  lon: -77,
  tz: "America/New_York",
};
jest.mock("../../src/api/hooks", () => ({
  usePlaces: () => ({ data: [place], isFetching: false, error: null }),
}));
test("disabled and busy buttons cannot submit", async () => {
  const onPress = jest.fn(),
    user = userEvent.setup();
  await render(<Button label="Save" disabled onPress={onPress} />);
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  await user.press(screen.getByRole("button", { name: "Save" }));
  expect(onPress).not.toHaveBeenCalled();
});
test("inputs and choice chips expose accessible names and state", async () => {
  await render(
    <>
      <Field label="Name" value="Ada" onChangeText={() => {}} />
      <Chip label="English" selected onPress={() => {}} />
    </>,
  );
  expect(screen.getByLabelText("Name")).toHaveDisplayValue("Ada");
  expect(screen.getByRole("radio", { name: "English" })).toBeChecked();
});
test("place selection requires explicit confirmation after candidate tap", async () => {
  await i18n.changeLanguage("en");
  const confirm = jest.fn(),
    user = userEvent.setup();
  await render(<PlaceSearch onConfirm={confirm} />);
  await user.type(screen.getByLabelText("Search city or town"), "Alex");
  await user.press(screen.getByText("Alexandria"));
  expect(screen.getByText("Virginia · United States")).toBeOnTheScreen();
  expect(confirm).not.toHaveBeenCalled();
  await user.press(
    screen.getByRole("button", { name: "Yes, this is the place" }),
  );
  expect(confirm).toHaveBeenCalledWith(place);
});
