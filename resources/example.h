/* SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include <memory>
#include <string>
#include <vector>

namespace outer { namespace inner {

class Base {
};

template<typename T, typename... Ts>
class Derived : public Base {
  Q_OBJECT

public:
  Derived() = delete;
  template<typename... Us>
  Derived(Us&&... us) : Base{} {
    ((void)us, ...);
  }
  Derived(int) : Base{} {
  }

  std::shared_ptr<std::string> method_decl() const volatile;

  int virtual virtual_method(float, std::string) {
    return 1;
  }

protected:
  float virtual pure_virtual_method(double a1, std::shared_ptr<std::vector<unsigned int>> a2) const = 0;

  void slot_decl(int, double, std::shared_ptr<int>) = 0;

private:
  template<typename U, typename... Us>
  U template_method(Us&&... us) {
    return U{std::forward<Us>(us)...};
  }

  static int static_method() {
    return 3;
  }

  void signal_decl(int, float, std::vector<int>);
};

}} // namespace outer::inner
