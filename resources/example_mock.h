#ifndef DRMOCK_MOCK_IMPLEMENTATIONSDerived
#define DRMOCK_MOCK_IMPLEMENTATIONSDerived

#define DRMOCK
#include <DrMock/Mock.h>
#include "/Users/malte/drmock-generator/resources/example.h"

namespace outer { namespace inner { namespace ns {

template<typename T, typename ... Ts>
class DRMOCK_OBJECTDerived
{
  friend class outer::inner::Derived<T, Ts ...>;
  std::shared_ptr<::drmock::StateObject> DRMOCK_STATE_OBJECT_{std::make_shared<::drmock::StateObject>()};
  std::shared_ptr<::drmock::Method<outer::inner::Derived<T, Ts ...>, int virtual, float, std :: string>> DRMOCK_METHOD_PTRvirtual_method_0{std::make_shared<::drmock::Method<outer::inner::Derived<T, Ts ...>, int virtual, float, std :: string>>("virtual_method", DRMOCK_STATE_OBJECT_)};
  std::shared_ptr<::drmock::Method<outer::inner::Derived<T, Ts ...>, float virtual, double, std :: shared_ptr < std :: vector < unsigned int >>>> DRMOCK_METHOD_PTRpure_virtual_method_0{std::make_shared<::drmock::Method<outer::inner::Derived<T, Ts ...>, float virtual, double, std :: shared_ptr < std :: vector < unsigned int >>>>("pure_virtual_method", DRMOCK_STATE_OBJECT_)};
  std::shared_ptr<::drmock::Method<outer::inner::Derived<T, Ts ...>, void, int, double, std :: shared_ptr < int >>> DRMOCK_METHOD_PTRslot_decl_0{std::make_shared<::drmock::Method<outer::inner::Derived<T, Ts ...>, void, int, double, std :: shared_ptr < int >>>("slot_decl", DRMOCK_STATE_OBJECT_)};

public:
  ::drmock::Controller ctrl{{DRMOCK_METHOD_PTRvirtual_method_0, DRMOCK_METHOD_PTRpure_virtual_method_0, DRMOCK_METHOD_PTRslot_decl_0}, DRMOCK_STATE_OBJECT_};

private:
  auto & DRMOCK_DISPATCHvirtual_method(::drmock::TypeContainer<float, std :: string>)
  {
    return *DRMOCK_METHOD_PTRvirtual_method_0;
  }
  auto & DRMOCK_DISPATCHpure_virtual_method(::drmock::TypeContainer<double, std :: shared_ptr < std :: vector < unsigned int >>, ::drmock::Const>)
  {
    return *DRMOCK_METHOD_PTRpure_virtual_method_0;
  }
  auto & DRMOCK_DISPATCHslot_decl(::drmock::TypeContainer<int, double, std :: shared_ptr < int >>)
  {
    return *DRMOCK_METHOD_PTRslot_decl_0;
  }

public:
  auto & virtual_method()
  {
    return DRMOCK_DISPATCHvirtual_method(::drmock::TypeContainer<float, std :: string>{});
  }
  auto & pure_virtual_method()
  {
    return DRMOCK_DISPATCHpure_virtual_method(::drmock::TypeContainer<double, std :: shared_ptr < std :: vector < unsigned int >>, ::drmock::Const>{});
  }
  auto & slot_decl()
  {
    return DRMOCK_DISPATCHslot_decl(::drmock::TypeContainer<int, double, std :: shared_ptr < int >>{});
  }
};

}}} // namespace outer::inner::ns

namespace outer { namespace inner { namespace ns {

template<typename T, typename ... Ts>
class DerivedMock : public outer::inner::Derived<T, Ts ...>
{

public:
  template<typename ... DRMOCK_FORWARDING_CTOR_TS>
  DerivedMock(DRMOCK_FORWARDING_CTOR_TS&&... ts) : outer::inner::Derived<T, Ts ...>{std::forward<DRMOCK_FORWARDING_CTOR_TS>(ts)...}
  {
    mock.virtual_method().parent(this);
    mock.pure_virtual_method().parent(this);
    mock.slot_decl().parent(this);
  }
  mutable outer::inner::ns::DRMOCK_OBJECTDerived<T, Ts ...> mock{};
  int virtual virtual_method(float a0, std :: string a1) override
  {
    auto& result = *mock.virtual_method().call(std::forward<float>(a0), std::forward<std :: string>(a1));
    return std::forward<int virtual>(::drmock::move_if_not_copy_constructible(result));
  }
  float virtual pure_virtual_method(double a0, std :: shared_ptr < std :: vector < unsigned int >> a1) const override
  {
    auto& result = *mock.pure_virtual_method().call(std::forward<double>(a0), std::forward<std :: shared_ptr < std :: vector < unsigned int >>>(a1));
    return std::forward<float virtual>(::drmock::move_if_not_copy_constructible(result));
  }
  void slot_decl(int a0, double a1, std :: shared_ptr < int > a2) override
  {
    mock.slot_decl().call(std::forward<int>(a0), std::forward<double>(a1), std::forward<std :: shared_ptr < int >>(a2));
  }
};

}}} // namespace outer::inner::ns

#endif /* DRMOCK_MOCK_IMPLEMENTATIONSDerived */