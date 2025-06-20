document.addEventListener("DOMContentLoaded", function () {
  // Automatically hide flash messages after 5 seconds
  const flashMessages = document.querySelectorAll(".flash-message");
  if (flashMessages.length > 0) {
    setTimeout(() => {
      flashMessages.forEach((message) => {
        message.classList.add("opacity-0");
        setTimeout(() => {
          message.remove();
        }, 300);
      });
    }, 5000);
  }

  // Enable dropdown menus
  const dropdownToggles = document.querySelectorAll(".dropdown-toggle");
  dropdownToggles.forEach((toggle) => {
    toggle.addEventListener("click", (e) => {
      e.preventDefault();
      const dropdown = toggle.nextElementSibling;
      dropdown.classList.toggle("hidden");

      // Close dropdown when clicking outside
      document.addEventListener("click", function closeDropdown(event) {
        if (
          !toggle.contains(event.target) &&
          !dropdown.contains(event.target)
        ) {
          dropdown.classList.add("hidden");
          document.removeEventListener("click", closeDropdown);
        }
      });
    });
  });

  // Enable mobile menu toggle
  const mobileMenuButton = document.getElementById("mobile-menu-button");
  const mobileMenu = document.getElementById("mobile-menu");

  if (mobileMenuButton && mobileMenu) {
    mobileMenuButton.addEventListener("click", () => {
      mobileMenu.classList.toggle("hidden");
    });
  }

  // Form validation
  const forms = document.querySelectorAll('form[data-validate="true"]');
  forms.forEach((form) => {
    form.addEventListener("submit", (e) => {
      let isValid = true;

      // Check required fields
      const requiredFields = form.querySelectorAll("[required]");
      requiredFields.forEach((field) => {
        if (!field.value.trim()) {
          isValid = false;
          field.classList.add("border-red-500");

          // Add error message if not exists
          let errorMessage = field.nextElementSibling;
          if (
            !errorMessage ||
            !errorMessage.classList.contains("error-message")
          ) {
            errorMessage = document.createElement("p");
            errorMessage.classList.add(
              "error-message",
              "text-red-500",
              "text-xs",
              "mt-1"
            );
            errorMessage.textContent = "This field is required";
            field.parentNode.insertBefore(errorMessage, field.nextSibling);
          }
        } else {
          field.classList.remove("border-red-500");

          // Remove error message if exists
          const errorMessage = field.nextElementSibling;
          if (
            errorMessage &&
            errorMessage.classList.contains("error-message")
          ) {
            errorMessage.remove();
          }
        }
      });

      if (!isValid) {
        e.preventDefault();
      }
    });
  });

  // Automatic textarea height adjustment
  const autoResizeTextareas = document.querySelectorAll(
    "textarea[data-autoresize]"
  );
  autoResizeTextareas.forEach((textarea) => {
    textarea.addEventListener("input", () => {
      textarea.style.height = "auto";
      textarea.style.height = textarea.scrollHeight + "px";
    });

    // Trigger once to set initial height
    textarea.dispatchEvent(new Event("input"));
  });

  // Copy to clipboard functionality
  const copyButtons = document.querySelectorAll("[data-copy]");
  copyButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const textToCopy = button.getAttribute("data-copy");

      navigator.clipboard
        .writeText(textToCopy)
        .then(() => {
          // Show success message
          const originalText = button.textContent;
          button.textContent = "Copied!";

          setTimeout(() => {
            button.textContent = originalText;
          }, 2000);
        })
        .catch((err) => {
          console.error("Failed to copy text: ", err);
        });
    });
  });

  // Check token on page load for protected pages
  const protectedPages = document.querySelectorAll('[data-protected="true"]');
  if (protectedPages.length > 0) {
    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "/login";
    }
  }
});
