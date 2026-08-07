import { render, screen } from "@testing-library/react";
import { App } from "../App";

describe("App shell", () => {
  it("renders the wordmark", () => {
    render(<App />);
    expect(screen.getByText("Provenance")).toBeInTheDocument();
  });

  it("carries the product descriptor, not the demo hook line", () => {
    render(<App />);
    expect(screen.getByText(/AI Trust Layer for Environmental Data/i)).toBeInTheDocument();
    expect(screen.queryByText(/Is This Real/i)).not.toBeInTheDocument();
  });
});
