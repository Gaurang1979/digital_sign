#ifndef SETTIMER_H
#define SETTIMER_H

#include "../../include/auxiliary.h"
class GetTimer
{
public:
	GetTimer();
	~GetTimer();
	CK_RV Connect();
	CK_RV Get();
protected:
	void *m_hPkiLib;
	AUX_FUNC_LIST_PTR m_pAuxFunc;
	CK_SLOT_ID_PTR m_pSlotList;
	CK_ULONG_PTR m_pTimerInfo;
};

#endif
