#ifndef SETTIMER_H
#define SETTIMER_H

#include "../../include/auxiliary.h"

class SetTimer
{
public:
	SetTimer();
	~SetTimer();
	CK_RV Connect();
	CK_RV Set(CK_ULONG);
protected:
	void *m_hPkiLib;
	AUX_FUNC_LIST_PTR m_pAuxFunc;
	CK_SLOT_ID_PTR m_pSlotList;
};

#endif
