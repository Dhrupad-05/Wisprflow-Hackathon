const details = document.querySelector("[data-step='details']");
const review = document.querySelector("[data-step='review']");
const otp = document.querySelector("[data-step='otp']");
const success = document.querySelector("[data-step='success']");

details.addEventListener("submit", (event) => {
  event.preventDefault();
  details.hidden = true;
  review.hidden = false;
});

review.querySelector("button").addEventListener("click", () => {
  review.hidden = true;
  otp.hidden = false;
});

otp.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = otp.querySelector("input").value;
  if (!/^\d{6}$/.test(value)) {
    otp.querySelector("small").textContent = "Enter any six digits for this demo.";
    return;
  }
  otp.hidden = true;
  success.hidden = false;
});
