self.__MIDDLEWARE_MATCHERS = [
  {
    "regexp": "^(?:\\/(_next\\/data\\/[^/]{1,}))?(?:\\/((?!_next|admin|api|robots\\.txt|sitemap\\.xml|icon\\.svg|favicon\\.ico|.*\\.[\\w]+$).*))(\\.json|\\.rsc|\\.segments\\/.+\\.segment\\.rsc)?[\\/#\\?]?$",
    "originalSource": "/((?!_next|admin|api|robots\\.txt|sitemap\\.xml|icon\\.svg|favicon\\.ico|.*\\.[\\w]+$).*)"
  }
];self.__MIDDLEWARE_MATCHERS_CB && self.__MIDDLEWARE_MATCHERS_CB()