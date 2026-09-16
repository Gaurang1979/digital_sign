

#include "SSF33Test.h"
#include "Common.h"

#define DATA_SIZE	32
#define BLOCK_SIZE	20
#define DEC_BLOCK_SIZE	16

Ssf33Test::Ssf33Test()
{
	m_hKey = 0;
}

Ssf33Test::~Ssf33Test()
{
}

void Ssf33Test::Test()
{
	GenerateKey();
	if(m_hKey == 0)
	{
		return ;
	}
	crypt_Single();
	crypt_Update();
}
void Ssf33Test::GenerateKey()
{
	do{
		SHOW_INFO("Generate Ssf33 key to test...");
		CK_OBJECT_CLASS oClass = CKO_SECRET_KEY;
		CK_KEY_TYPE keyType = CKK_SSF33; 
		CK_BBOOL bTrue = true;
		CK_BBOOL bFalse = false;
		CK_ULONG ulLen = 16;
		CK_MECHANISM mechanism = {CKM_SSF33_KEY_GEN, NULL_PTR, 0};
		CK_ATTRIBUTE Ssf33tem[] = {
			{CKA_CLASS, &oClass, sizeof(CK_OBJECT_CLASS)},
			{CKA_KEY_TYPE, &keyType, sizeof(CK_KEY_TYPE)},
			{CKA_TOKEN, &bFalse, sizeof(CK_BBOOL)},
			{CKA_PRIVATE, &bTrue, sizeof(CK_BBOOL)},
			{CKA_ENCRYPT, &bTrue, sizeof(CK_BBOOL)},
			{CKA_DECRYPT, &bTrue, sizeof(CK_BBOOL)},
			{CKA_VALUE_LEN, &ulLen, sizeof(CK_ULONG)}, 
		};
		CK_ULONG ulCount = sizeof(Ssf33tem)/sizeof(CK_ATTRIBUTE);
		//generate key:
		START_OP("generate SSF33 key...")
			CK_RV rv =  m_gToken->C_GenerateKey(hSession, &mechanism, Ssf33tem, ulCount, &m_hKey); 
		CHECK_OP(rv)
	}while(0);
}
void Ssf33Test::crypt_Single()
{
	const CK_ULONG DATA_LENGTH = 1024*3;
	CK_BYTE bIn[DATA_LENGTH] = {0}, bTemp[DATA_LENGTH] = {0}, bOut[DATA_LENGTH] = {0};
	CK_ULONG ulIn = 0, ulOut = 0, ulTemp = 0;
	CK_ULONG Mechanism[3] = {CKM_SSF33_CBC, CKM_SSF33_ECB, CKM_SSF33_CBC_PAD};
	CK_BYTE_PTR bHint[3] = {(CK_BYTE_PTR)"CKM_SSF33_CBC: ",\
							(CK_BYTE_PTR)"CKM_SSF33_ECB: ",
							(CK_BYTE_PTR)"CKM_SSF33_CBC_PAD: "};
	SHOW_INFO("\nSSF33: C_Encrypt/C_Decrypt: \n");
	do{
		for(int i=0;i<3;i++)
		{
			for (i != 2 ? ulIn = SSF33_BLOCK_LEN : ulIn = 0; ulIn < 32; i != 2 ? ulIn += SSF33_BLOCK_LEN : ++ulIn)
			{
				for(register CK_ULONG i0 = 0;i0<ulIn;i0++)
					bIn[i0] = (CK_BYTE)i0;
				
				
				SHOW_INFO("\n********************************\n");
				SHOW_INFO(bHint[i]);
				//ecnrypt init:
				CK_BYTE iv[16] = {'*','2','1','0','4','z','y','b','*','2','1','0','4','z','y','b'};
				CK_MECHANISM ckMechanism = {Mechanism[i], iv, 16};
				START_OP("Encrypting initialize.")  
				CK_RV rv =  m_gToken->C_EncryptInit(hSession, &ckMechanism, m_hKey); 
				CHECK_OP(rv)

				START_OP("Encrypt the message.")
				//Get the encrypted buffer's size:
				//{{{Here, I do not invoke "C_Encrypt" twice for I had declared bTemp with a size=1024.
				//If you do not declare the result's buffer previous,
				//you should invoke twice to get the buffer's size, such as:[Decrypt is similar]
				rv =  m_gToken->C_Encrypt(hSession, bIn, ulIn, NULL, &ulTemp);
				//}}}
				CHECK_RV("C_Encrypt[get buffer's size]", rv);
				//encrypt:
				rv =  m_gToken->C_Encrypt(hSession, bIn, ulIn, bTemp, &ulTemp);
				CHECK_RV("C_Encrypt", rv);
				CHECK_OP(rv);
				SHOW_INFO("Data encrypted: \n");
				ShowData(bTemp, ulTemp);

				START_OP("Decrypting initialize.");
				rv =  m_gToken->C_DecryptInit(hSession, &ckMechanism, m_hKey);
				CHECK_OP(rv);
				START_OP("Decrypt the message.");
				//Get buffer's size:
				rv =  m_gToken->C_Decrypt(hSession, bTemp, ulTemp, NULL, &ulOut);
				//Get decrypted data:
				rv =  m_gToken->C_Decrypt(hSession, bTemp, ulTemp, bOut, &ulOut);
				CHECK_OP(rv);
				SHOW_INFO("Data decrypted: \n");
				ShowData(bOut, ulOut);
				
				START_OP("Compare the original message and decrypted data: ");
				if(0 == memcmp(bIn, bOut, ulOut))
				{
					CHECK_OP(CKR_OK);
				}
				else
				{
					SHOW_INFO("....[FAILED]\n");
				}
			}
		}
	}while(0);

}

void Ssf33Test::crypt_Update()
{
	const CK_ULONG DATA_LENGTH = 1024*3;
	CK_BYTE bIn[DATA_LENGTH] = {0}, bTemp[DATA_LENGTH] = {0}, bOut[DATA_LENGTH] = {0};
	CK_ULONG ulIn = 0, ulOut = 0, ulTemp = 0;
	CK_ULONG Mechanism[3] = {CKM_SSF33_CBC, CKM_SSF33_ECB, CKM_SSF33_CBC_PAD};
	CK_BYTE_PTR bHint[3] = {(CK_BYTE_PTR)"CKM_SSF33_CBC: ",\
									(CK_BYTE_PTR)"CKM_SSF33_ECB: ",\
									(CK_BYTE_PTR)"CKM_SSF33_CBC_PAD: "};
	SHOW_INFO("\n********************************\n");
	do{
		for(int i=0;i<3;i++)
		{
			for (i != 2 ? ulIn = SSF33_BLOCK_LEN : ulIn = 0; ulIn < 32; i != 2 ? ulIn += SSF33_BLOCK_LEN : ++ulIn)
			{			
				for(register CK_ULONG i0 = 0;i0<ulIn;i0++)
					bIn[i0] = (CK_BYTE)i0;

				SHOW_INFO("\n");
				SHOW_INFO("\nSSF33: C_EncryptUpdate/C_DecryptUpdate: \n");
				SHOW_INFO(bHint[i]);
				//ecnrypt init:
				CK_BYTE iv[16] = {'*','2','1','0','4','z','y','b','*','2','1','0','4','z','y','b'};
				CK_MECHANISM ckMechanism = {Mechanism[i], iv, sizeof(iv)};
				START_OP("Encrypting initialize.")  
					CK_RV rv =  m_gToken->C_EncryptInit(hSession, &ckMechanism, m_hKey); 
				CHECK_OP(rv)
				
				CK_ULONG ulEncrypted = 0;
				START_OP("Encrypt the message.");


				unsigned long dwLoop = ulIn / BLOCK_SIZE;
				unsigned long dwLeft = ulIn % BLOCK_SIZE;
				unsigned long iii = 0;
				CK_BYTE_PTR pRetData = bTemp;
				for(iii = 0; iii < dwLoop ;++iii)
				{
					rv =  m_gToken->C_EncryptUpdate(hSession, bIn + BLOCK_SIZE * iii, BLOCK_SIZE, NULL, &ulTemp);//get buffer's size.
					rv =  m_gToken->C_EncryptUpdate(hSession, bIn + BLOCK_SIZE * iii, BLOCK_SIZE, pRetData, &ulTemp);
					pRetData += ulTemp;
					ulEncrypted+=ulTemp;
					CHECK_RV("C_Encrypt[inside loop]", rv);
				}
				if(0 != dwLeft)
				{
					rv =  m_gToken->C_EncryptUpdate(hSession, bIn + BLOCK_SIZE * iii, dwLeft, NULL, &ulTemp);//get buffer's size.
					rv =  m_gToken->C_EncryptUpdate(hSession, bIn + BLOCK_SIZE * iii, dwLeft, pRetData, &ulTemp);
					pRetData += ulTemp;
					ulEncrypted+=ulTemp;
					CHECK_RV("C_Encrypt[last block]", rv);
				}

				START_OP("C_EncryptFinal...");
				rv = m_gToken->C_EncryptFinal(hSession, NULL, &ulTemp);
				rv = m_gToken->C_EncryptFinal(hSession, pRetData, &ulTemp);
				CHECK_OP(rv);
				ulEncrypted+=ulTemp;
				ulTemp = 0;
				SHOW_INFO("Data encrypted: \n");
				ShowData(bTemp, ulEncrypted);

	//-------------------------------------------------------------------------//
				
				START_OP("Decrypting initialize.");
				CK_BYTE iv1[16] = {'*','2','1','0','4','z','y','b','*','2','1','0','4','z','y','b'};	
				CK_MECHANISM ckMechanism1 = {Mechanism[i], iv1, sizeof(iv1)};
				rv =  m_gToken->C_DecryptInit(hSession, &ckMechanism1, m_hKey);
				CHECK_OP(rv);
				START_OP("Decrypt the message.");

				dwLoop = ulEncrypted / DEC_BLOCK_SIZE;
	//			dwLeft = ulEncrypted % DEC_BLOCK_SIZE;

				iii = 0;
				pRetData = bOut;
				CK_ULONG ulDecrypt = 0;
				for(iii = 0; iii < dwLoop ;++iii)
				{
					rv =  m_gToken->C_DecryptUpdate(hSession, bTemp + DEC_BLOCK_SIZE * iii, DEC_BLOCK_SIZE, NULL, &ulTemp);//get buffer's size.
					rv =  m_gToken->C_DecryptUpdate(hSession, bTemp + DEC_BLOCK_SIZE * iii, DEC_BLOCK_SIZE, pRetData, &ulTemp);
					pRetData += ulTemp;
					ulDecrypt+=ulTemp;
					CHECK_RV("C_Decrypt[inside loop]", rv);
				}
				START_OP("C_DecryptFinale...");
				rv = m_gToken->C_DecryptFinal(hSession, NULL, &ulTemp);
				rv = m_gToken->C_DecryptFinal(hSession, pRetData, &ulTemp);
				CHECK_OP(rv);
				ulDecrypt += ulTemp;
				
				SHOW_INFO("Data decrypted: \n");
				ShowData(bOut, ulDecrypt);
				
				START_OP("Compare the original message and decrypted data: ");
				if(0 == memcmp(bIn, bOut, ulDecrypt))
				{
					CHECK_OP(CKR_OK);
				}
				else
				{
					SHOW_INFO("....[FAILED]\n");
				}
			}
		}
	}while(0);
}
