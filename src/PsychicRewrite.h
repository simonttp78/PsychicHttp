#ifndef PsychicRewrite_h
#define PsychicRewrite_h

#include "PsychicCore.h"

/*
 * REWRITE :: One instance can be handle any Request (done by the Server)
 * */

class PsychicRewrite
{
  protected:
    std::string _fromPath;
    std::string _toUri;
    std::string _toPath;
    std::string _toParams;
    PsychicRequestFilterFunction _filter;

  public:
    PsychicRewrite(const char* from, const char* to);
    virtual ~PsychicRewrite();

    PsychicRewrite* setFilter(PsychicRequestFilterFunction fn);
    bool filter(PsychicRequest* request) const;
    const char* from(void) const;
    const char* toUrl(void) const;
    const char* params(void) const;
    virtual bool match(PsychicRequest* request);
};

#endif